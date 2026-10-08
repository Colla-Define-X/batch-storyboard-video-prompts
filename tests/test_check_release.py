from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_release.py"
SPEC = importlib.util.spec_from_file_location("check_release_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
check_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_release)


class ReleaseCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "skill"
        for relative in check_release.REQUIRED_PATHS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("sample\n", encoding="utf-8")
        (self.root / "VERSION").write_text("1.1.0\n", encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text("## [1.1.0]\n", encoding="utf-8")
        (self.root / "SKILL.md").write_text(
            "---\nname: batch-storyboard-video-prompts\ndescription: Test\n---\n",
            encoding="utf-8",
        )

    def run_check(self, *args: str) -> str:
        output = io.StringIO()
        with patch.object(check_release, "ROOT", self.root), contextlib.redirect_stdout(output):
            check_release.main(list(args))
        return output.getvalue()

    def git(self, *args: str, root: Path | None = None) -> None:
        result = subprocess.run(
            ["git", "-C", str(root or self.root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(f"Git command failed: {args!r}\n{result.stderr}")

    def init_repo(self, root: Path | None = None) -> None:
        target = root or self.root
        result = subprocess.run(["git", "init", "-q", str(target)], capture_output=True, text=True)
        if result.returncode != 0:
            self.fail(result.stderr)

    def commit(self, message: str = "snapshot", root: Path | None = None) -> None:
        self.git(
            "-c", "user.name=Release Test",
            "-c", "user.email=release@example.test",
            "-c", "commit.gpgsign=false",
            "commit", "-qm", message,
            root=root,
        )

    def commit_required(self) -> None:
        self.init_repo()
        self.git("add", "--", *check_release.REQUIRED_PATHS)
        self.commit()

    def test_local_check_needs_no_git_or_git_invocation(self) -> None:
        with patch.object(check_release.subprocess, "run", side_effect=AssertionError("Git was called")):
            self.assertIn("OK: batch-storyboard-video-prompts", self.run_check())
        with self.assertRaisesRegex(SystemExit, "(own Git repository|skill root to be the Git root)"):
            self.run_check("--release")

    def test_release_reports_missing_git_and_head(self) -> None:
        with patch.object(check_release.subprocess, "run", side_effect=FileNotFoundError("git missing")):
            with self.assertRaisesRegex(SystemExit, "requires Git"):
                self.run_check("--release")
        self.init_repo()
        with self.assertRaisesRegex(SystemExit, "HEAD commit"):
            self.run_check("--release")

    def test_spec_must_be_committed_not_merely_present_or_staged(self) -> None:
        self.init_repo()
        self.git("add", "--", *(path for path in check_release.REQUIRED_PATHS if path != "SPEC.md"))
        self.commit("without spec")
        self.assertIn("OK:", self.run_check())
        with self.assertRaisesRegex(SystemExit, "SPEC.md"):
            self.run_check("--release")
        self.git("add", "--", "SPEC.md")
        with self.assertRaisesRegex(SystemExit, "SPEC.md"):
            self.run_check("--release")
        self.commit("add spec")
        self.assertIn("OK:", self.run_check("--release"))

    def test_missing_runtime_requirements_fails_local_check(self) -> None:
        (self.root / "requirements.txt").unlink()
        with self.assertRaisesRegex(SystemExit, "Missing required files: requirements.txt"):
            self.run_check()

    def test_runtime_requirements_must_be_committed_not_merely_staged(self) -> None:
        self.init_repo()
        self.git("add", "--", *(path for path in check_release.REQUIRED_PATHS if path != "requirements.txt"))
        self.commit("without runtime requirements")
        self.assertIn("OK:", self.run_check())
        with self.assertRaisesRegex(SystemExit, "requirements.txt"):
            self.run_check("--release")
        self.git("add", "--", "requirements.txt")
        with self.assertRaisesRegex(SystemExit, "requirements.txt"):
            self.run_check("--release")
        self.commit("add runtime requirements")
        self.assertIn("OK:", self.run_check("--release"))

    def test_staged_and_unstaged_required_changes_are_rejected(self) -> None:
        self.commit_required()
        readme = self.root / "README.md"
        original = readme.read_text(encoding="utf-8")
        readme.write_text(original + "unstaged\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "staged or unstaged"):
            self.run_check("--release")
        readme.write_text(original + "staged\n", encoding="utf-8")
        self.git("add", "--", "README.md")
        with self.assertRaisesRegex(SystemExit, "staged or unstaged"):
            self.run_check("--release")
        readme.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "staged or unstaged"):
            self.run_check("--release")

    def test_parent_git_repository_is_not_skill_repository(self) -> None:
        self.init_repo(self.base)
        self.git("add", "--", "skill", root=self.base)
        self.commit(root=self.base)
        with self.assertRaisesRegex(SystemExit, "skill root to be the Git root"):
            self.run_check("--release")

    def test_unrelated_work_does_not_block_release(self) -> None:
        self.commit_required()
        notes = self.root / "notes.txt"
        notes.write_text("old\n", encoding="utf-8")
        self.git("add", "--", "notes.txt")
        self.commit("add unrelated notes")
        notes.write_text("edited\n", encoding="utf-8")
        (self.root / "other-untracked.txt").write_text("new\n", encoding="utf-8")
        self.assertIn("OK:", self.run_check("--release"))

    def test_head_directory_does_not_count_as_required_file(self) -> None:
        spec = self.root / "SPEC.md"
        spec.unlink()
        spec.mkdir()
        (spec / "inside.txt").write_text("nested\n", encoding="utf-8")
        self.init_repo()
        self.git("add", "--", *(path for path in check_release.REQUIRED_PATHS if path != "SPEC.md"), "SPEC.md")
        self.commit("spec path is a directory")
        (spec / "inside.txt").unlink()
        spec.rmdir()
        spec.write_text("# Current behavior\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "SPEC.md"):
            self.run_check("--release")


if __name__ == "__main__":
    unittest.main()
