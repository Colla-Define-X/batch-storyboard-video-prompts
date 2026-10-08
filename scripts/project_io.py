"""Serialized project mutations with recoverable multi-file rollback."""
from __future__ import annotations

import base64
import contextlib
from contextvars import ContextVar
import functools
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path


_active_transaction = ContextVar('storyboard_transaction', default=None)


def digest(content: bytes | None) -> str | None:
    return hashlib.sha256(content).hexdigest() if content is not None else None


def current_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def inside(root: Path, relative: str | Path) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError(f'Path escapes project: {relative}')
    return path


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows scanners can briefly hold the journal between atomic writes.
        for attempt in range(10):
            try:
                temp.replace(path)
                break
            except PermissionError as exc:
                if os.name != 'nt' or getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == 9:
                    raise
                time.sleep(.05)
    finally:
        temp.unlink(missing_ok=True)


def atomic_bytes(path: Path, content: bytes) -> None:
    state = _active_transaction.get()
    if state is not None:
        path = inside(state['root'], path.resolve())
        relative = str(path.relative_to(state['root']))
        files = state['journal']['files']
        if relative not in files:
            before = current_bytes(path)
            files[relative] = {'before': base64.b64encode(before).decode('ascii') if before is not None else None,
                               'written_hashes': []}
        files[relative]['written_hashes'].append(digest(content))
        # Write-ahead logging covers only files this operation actually writes.
        _atomic_bytes(state['path'], json.dumps(state['journal']).encode('utf-8'))
    _atomic_bytes(path, content)


@contextlib.contextmanager
def project_lock(root: Path):
    if not root.is_dir():
        raise FileNotFoundError(root)
    path = inside(root, '.workflow.lock')
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        deadline = time.monotonic() + 10
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Project is busy; retry after the current command finishes')
                time.sleep(.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def recover(root: Path) -> None:
    journal = inside(root, '.workflow-transaction.json')
    if not journal.exists():
        return
    saved = json.loads(journal.read_text(encoding='utf-8'))
    if saved.get('format') != 2:
        raise RuntimeError('Legacy transaction journal needs manual recovery; preserve the journal and current files')
    restore = []
    for relative, record in saved['files'].items():
        path = inside(root, relative)
        before = base64.b64decode(record['before'], validate=True) if record['before'] is not None else None
        permitted = {digest(before), *record['written_hashes']}
        if digest(current_bytes(path)) not in permitted:
            raise RuntimeError(f'Recovery conflict at {relative}; preserve current files and journal for manual reconciliation')
        restore.append((path, before, permitted))
    # Check every target before restoring any of them. Repeated recovery is safe.
    for path, before, permitted in restore:
        if digest(current_bytes(path)) not in permitted:
            raise RuntimeError(f'Recovery conflict at {path}; preserve current files and journal')
        if before is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_bytes(path, before)
    journal.unlink()


def transaction(function):
    @functools.wraps(function)
    def call(root: Path, *args, **kwargs):
        root = root.resolve()
        with project_lock(root):
            recover(root)
            if function.__name__ != 'migrate':
                project = json.loads((root/'project.json').read_text(encoding='utf-8'))
                if project.get('schema_version') != 4:
                    raise ValueError('Mutation requires schema v4; run migrate first')
            journal = inside(root, '.workflow-transaction.json')
            saved = {'format': 2, 'files': {}}
            _atomic_bytes(journal, json.dumps(saved).encode('utf-8'))
            token = _active_transaction.set({'root': root, 'path': journal, 'journal': saved})
            try:
                result = function(root, *args, **kwargs)
                for relative, record in saved['files'].items():
                    if digest(current_bytes(inside(root, relative))) != record['written_hashes'][-1]:
                        raise RuntimeError(f'Concurrent write conflict at {relative}')
            except BaseException:
                recover(root)
                raise
            finally:
                _active_transaction.reset(token)
            journal.unlink()
            return result
    return call


def consistent_read(function):
    @functools.wraps(function)
    def call(root: Path, *args, **kwargs):
        root = root.resolve()
        with project_lock(root):
            recover(root)
            return function(root, *args, **kwargs)
    return call
