#!/usr/bin/env python3
"""Validate repository structure and release metadata."""

from __future__ import annotations

import py_compile
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = (
    "SKILL.md",
    "README.md",
    "CHANGELOG.md",
    "VERSION",
    "agents/openai.yaml",
    "references/prompt-templates.md",
    "references/schema.md",
    "references/strict-mode.md",
    "scripts/reference_preview.py",
    "scripts/storyboard_layout.py",
    "scripts/workflow.py",
)
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def main() -> None:
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

    print(f"OK: batch-storyboard-video-prompts v{version}")


if __name__ == "__main__":
    main()
