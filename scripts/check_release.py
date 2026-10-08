#!/usr/bin/env python3
"""Validate repository structure and release metadata."""

from __future__ import annotations

import argparse
import os
import py_compile
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = (
    "SKILL.md",
    "README.md",
    "SPEC.md",
    "CHANGELOG.md",
    "VERSION",
    "requirements.txt",
    "agents/openai.yaml",
    "references/prompt-templates.md",
    "references/hybrid-coordination.md",
    "references/schema.md",
    "references/strict-mode.md",
    "scripts/reference_preview.py",
    "scripts/storyboard_layout.py",
    "scripts/check_release.py",
    "scripts/workflow.py",
    "scripts/project_io.py",
    "references/execution.md",
)
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def git_result(*args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise SystemExit(f"Release check requires Git: {exc}") from exc


def check_release_commit() -> None:
    top = git_result("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise SystemExit("Release check requires this skill to be its own Git repository")
    repo_root = Path(os.fsdecode(top.stdout).strip()).resolve()
    if repo_root != ROOT.resolve():
        raise SystemExit(f"Release check requires the skill root to be the Git root, not {repo_root}")

    head = git_result("rev-parse", "--verify", "HEAD^{commit}")
    if head.returncode != 0:
        raise SystemExit("Release check requires a HEAD commit")
    commit = os.fsdecode(head.stdout).strip()

    tree = git_result("ls-tree", "-r", "-z", "--full-tree", commit)
    if tree.returncode != 0:
        raise SystemExit("Could not inspect required files in HEAD")
    committed_files = {}
    for entry in tree.stdout.split(b"\0"):
        if entry:
            metadata, _, path = entry.partition(b"\t")
            committed_files[os.fsdecode(path)] = metadata.split(b" ")[1]
    missing = [path for path in REQUIRED_PATHS if committed_files.get(path) != b"blob"]
    if missing:
        raise SystemExit(f"Required files are not committed in HEAD: {', '.join(missing)}")

    for args in (
        ("diff", "--cached", "--quiet", commit, "--", *REQUIRED_PATHS),
        ("diff", "--quiet", "--", *REQUIRED_PATHS),
    ):
        diff = git_result(*args)
        if diff.returncode == 1:
            raise SystemExit("Required files have staged or unstaged changes relative to HEAD")
        if diff.returncode != 0:
            raise SystemExit("Could not compare required files with HEAD")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="also verify required files in this repository's HEAD")
    args = parser.parse_args(argv)

    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit(f"Missing required files: {', '.join(missing)}")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(version):
        raise SystemExit(f"VERSION is not valid SemVer: {version!r}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog:
        raise SystemExit(f"CHANGELOG.md has no entry for {version}")

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not skill.startswith("---\n") or "\nname: batch-storyboard-video-prompts\n" not in skill:
        raise SystemExit("SKILL.md front matter is missing the expected skill name")
    if "\ndescription:" not in skill.split("---", 2)[1]:
        raise SystemExit("SKILL.md front matter has no description")

    for script in (ROOT / "scripts").glob("*.py"):
        py_compile.compile(str(script), doraise=True)

    if args.release:
        check_release_commit()

    print(f"OK: batch-storyboard-video-prompts v{version}")


if __name__ == "__main__":
    main()
