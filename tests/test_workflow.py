from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import workflow  # noqa: E402


class WorkflowTests(unittest.TestCase):
    def test_project_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "project"
            workflow.init_project(project, "demo", 2)

            source = base / "product.jpg"
            source.write_bytes(b"stable-image-content")
            workflow.add_source(project, source, "image-01")

            workflow.set_status(project, "shot-01", "storyboard_prompt_pending", coordinator=False)
            workflow.sync_statuses(project)
            workflow.register_task(project, "shot-01", "thread-123", "host-456")
            workflow.validate(project)

            manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 3)
            self.assertEqual(manifest["shots"][0]["status"], "storyboard_prompt_pending")
            self.assertEqual(manifest["shots"][0]["task"]["thread_id"], "thread-123")
            self.assertEqual(
                manifest["assets"][0]["sha256"],
                hashlib.sha256(b"stable-image-content").hexdigest(),
            )

    def test_init_rejects_non_positive_shot_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                workflow.init_project(Path(directory) / "project", "demo", 0)


if __name__ == "__main__":
    unittest.main()
