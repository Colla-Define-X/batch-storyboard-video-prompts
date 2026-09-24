"""Serialized project mutations with recoverable multi-file rollback."""
from __future__ import annotations

import base64
import contextlib
import functools
import json
import os
import tempfile
import time
from pathlib import Path


def inside(root: Path, relative: str | Path) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError(f'Path escapes project: {relative}')
    return path


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


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


def controlled_paths(root: Path) -> list[Path]:
    paths = [root/'project.json', root/'project.json.bak', root/'shared-brief.md']
    for directory in (root/'shots').glob('*'):
        if directory.is_dir():
            paths.extend(directory/name for name in ('shot.json', 'shot.json.bak', 'state.json', 'storyboard-final.png', 'storyboard-final.json'))
    return [inside(root, p.relative_to(root)) for p in paths]


def recover(root: Path) -> None:
    journal = inside(root, '.workflow-transaction.json')
    if not journal.exists():
        return
    saved = json.loads(journal.read_text(encoding='utf-8'))
    for relative, encoded in saved.items():
        path = inside(root, relative)
        if encoded is None:
            path.unlink(missing_ok=True)
        else:
            atomic_bytes(path, base64.b64decode(encoded, validate=True))
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
            saved = {str(p.relative_to(root)): base64.b64encode(p.read_bytes()).decode('ascii') if p.exists() else None
                     for p in controlled_paths(root)}
            if function.__name__ == 'add_source':
                source = args[0] if args else kwargs['source']
                asset_id = args[1] if len(args) > 1 else kwargs['asset_id']
                target = inside(root, Path('sources') / f'{asset_id}{source.suffix.lower()}')
                # Include newly stabilized media in crash rollback without copying unrelated media.
                saved[str(target.relative_to(root))] = base64.b64encode(target.read_bytes()).decode('ascii') if target.exists() else None
            atomic_bytes(journal, json.dumps(saved).encode('utf-8'))
            try:
                result = function(root, *args, **kwargs)
            except BaseException:
                recover(root)
                raise
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
