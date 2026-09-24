from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import workflow  # noqa: E402


def make_image(path: Path, color: str = "red") -> None:
    Image.new("RGB", (16, 16), color).save(path)


def prepare(project: Path, sid="shot-01") -> None:
    manifest = workflow.read_json(project / "project.json")
    if not manifest.get("assets"):
        source = project / "input.png"
        make_image(source)
        workflow.add_source(project, source, "image-01")
    (project / "shared-brief.md").write_text("Approved wooden desk and daylight", encoding="utf-8")
    data = workflow.read_json(workflow.shot_json_path(project, sid))
    boundaries = manifest["defaults"]["time_boundaries_seconds"]
    data.update(references=[{"id": "image-01", "roles": ["product_identity"]}], sequence_type="cuts")
    data["panels"] = [dict(position=position, start_seconds=boundaries[i], end_seconds=boundaries[i+1],
                          time=f"{boundaries[i]}–{boundaries[i+1]}秒", label="外观展示", description="产品在木桌上")
                      for i, position in enumerate(workflow.POSITIONS)]
    workflow.write_json(workflow.shot_json_path(project, sid), data)
    (project / "shots" / sid / "storyboard-prompt.md").write_text("四宫格9:16，产品以image-01为准；四阶段展示外观、结构、使用细节和定格。奶油色标签。", encoding="utf-8")


def record_image(project: Path, sid="shot-01") -> None:
    workflow.preflight(project, sid)
    path = workflow.shot_json_path(project, sid)
    data = workflow.read_json(path)
    Image.new("RGB", (90, 160), "blue").save(path.parent / f"storyboard-review-v{data['storyboard_version']:02d}.png")
    data["qa"] = {"result": "pass", "notes": []}
    workflow.write_json(path, data)


class WorkflowTests(unittest.TestCase):
    def test_default_duration_uses_four_one_second_panels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 1)
            manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["defaults"]["duration_seconds"], 4)
            self.assertEqual(manifest["defaults"]["duration_policy"]["typical_range_seconds"], [4, 10])
            self.assertEqual(manifest["defaults"]["time_boundaries_seconds"], [0, 1, 2, 3, 4])

    def test_staged_project_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "project"
            workflow.init_project(project, "demo", 2, 5, "storyboard_and_video_prompt")
            workflow.set_concurrency(project, "pilot", 1)
            workflow.register_task(project, "shot-01", "thread-123", "host-456")

            source = base / "product.jpg"
            make_image(source)
            workflow.add_source(project, source, "image-01")

            workflow.set_status(project, "shot-01", "storyboard_prompt_pending", coordinator=True)
            prepare(project)
            workflow.approve(project, "shot-01", "storyboard_prompt", None)
            record_image(project)
            workflow.set_status(project, "shot-01", "storyboard_review_pending", coordinator=True)
            workflow.approve(project, "shot-01", "storyboard", "画面通过")
            (project / "shots/shot-01/video-prompt.md").write_text("Approved video guidance", encoding="utf-8")
            workflow.set_status(project, "shot-01", "video_prompt_review_pending", coordinator=True)
            workflow.approve(project, "shot-01", "video_prompt", None)
            workflow.validate(project)

            manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
            shot = json.loads((project / "shots/shot-01/shot.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 4)
            self.assertEqual(manifest["defaults"]["time_boundaries_seconds"], [0, 1, 2.5, 4, 5])
            self.assertEqual(manifest["shots"][0]["status"], "complete")
            self.assertEqual(manifest["shots"][0]["task"]["thread_id"], "thread-123")
            self.assertFalse(manifest["shots"][0]["task"]["active"])
            self.assertEqual([item["stage"] for item in shot["approvals"]], [
                "storyboard_prompt", "storyboard", "video_prompt",
            ])
            self.assertEqual(
                manifest["assets"][0]["sha256"],
                hashlib.sha256((project / "sources/image-01.jpg").read_bytes()).hexdigest(),
            )

    def test_default_mode_cannot_jump_to_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 1)
            with self.assertRaisesRegex(ValueError, "Invalid staged transition"):
                workflow.set_status(project, "shot-01", "complete", coordinator=True)

    def test_fast_mode_requires_explicit_reason_and_uses_combined_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 1)
            with self.assertRaisesRegex(ValueError, "requires the user's explicit request"):
                workflow.set_review_mode(project, "shot-01", "fast", None)

            workflow.set_review_mode(project, "shot-01", "fast", "用户要求直接生成")
            prepare(project)
            workflow.set_status(project, "shot-01", "running", coordinator=True)
            record_image(project)
            workflow.set_status(project, "shot-01", "review_pending", coordinator=True)
            workflow.approve(project, "shot-01", "review_package", "完整审核包通过")
            workflow.validate(project)

            shot = json.loads((project / "shots/shot-01/shot.json").read_text(encoding="utf-8"))
            self.assertEqual(shot["review_mode"], "fast")
            self.assertEqual(shot["review_mode_source"], "explicit_user_request")
            self.assertEqual(shot["status"], "complete")

    def test_rejects_short_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "at least 4 seconds"):
                workflow.init_project(Path(directory) / "project", "demo", 1, 3)

    def test_concurrency_requires_user_choice_and_supports_pilot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 3)
            manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertTrue((project / "shared-brief.md").is_file())
            self.assertIsNone(manifest["workflow"]["parallel_launch_mode"])
            self.assertIsNone(manifest["workflow"]["max_parallel_shot_tasks"])
            self.assertEqual(manifest["workflow"]["video_prompt_owner"], "current_conversation")

            with self.assertRaisesRegex(ValueError, "Concurrency choice is not recorded"):
                workflow.register_task(project, "shot-01", "thread-1", None)

            workflow.set_concurrency(project, "pilot", 2)
            workflow.register_task(project, "shot-01", "thread-1", None)
            workflow.register_task(project, "shot-02", "thread-2", None)
            workflow.set_status(project, "shot-01", "storyboard_prompt_pending", coordinator=False)
            with self.assertRaisesRegex(ValueError, "No shot-task slot available"):
                workflow.register_task(project, "shot-03", "thread-3", None)

            board = workflow.dashboard(project)
            brief = workflow.task_brief(project, "shot-01")
            self.assertIn("shot-01", board)
            self.assertIn("提示词待确认", board)
            self.assertIn(str((project / "shared-brief.md").resolve()), brief)
            self.assertIn("不要重新解释或复制全局规则", brief)
            self.assertIn("不要自动重试", brief)

            workflow.release_task(project, "shot-01")
            workflow.register_task(project, "shot-03", "thread-3", None)
            workflow.validate(project)

    def test_all_shots_concurrency_uses_project_shot_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 3)
            workflow.set_concurrency(project, "all")
            for index in range(1, 4):
                workflow.register_task(project, f"shot-{index:02d}", f"thread-{index}", None)
            manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["workflow"]["parallel_launch_mode"], "all")
            self.assertEqual(manifest["workflow"]["max_parallel_shot_tasks"], 3)
            workflow.validate(project)

    def test_failed_generation_requires_explicit_retry_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 1)
            workflow.set_status(project, "shot-01", "storyboard_prompt_pending", coordinator=True)
            prepare(project)
            workflow.approve(project, "shot-01", "storyboard_prompt", None)
            workflow.set_status(project, "shot-01", "generation_failed", coordinator=True)
            with self.assertRaisesRegex(ValueError, "Invalid staged transition"):
                workflow.set_status(project, "shot-01", "storyboard_generating", coordinator=True)
            with self.assertRaisesRegex(ValueError, "explicit request"):
                workflow.retry_shot(project, "shot-01", "storyboard_generating", None)
            workflow.retry_shot(project, "shot-01", "storyboard_generating", "用户要求重新生成")
            shot = json.loads((project / "shots/shot-01/shot.json").read_text(encoding="utf-8"))
            self.assertEqual(shot["status"], "storyboard_generating")
            self.assertEqual(shot["retries"][0]["reason"], "用户要求重新生成")

    def test_rejects_path_escape_duplicate_id_and_invalid_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "project"
            workflow.init_project(project, "demo", 1)
            jpg = base / "a.jpg"
            png = base / "b.png"
            make_image(jpg)
            make_image(png, "blue")

            with self.assertRaisesRegex(ValueError, "Asset ID"):
                workflow.add_source(project, jpg, "../escaped")
            workflow.add_source(project, jpg, "same-id")
            with self.assertRaisesRegex(ValueError, "Duplicate asset ID"):
                workflow.add_source(project, png, "same-id")

            invalid = base / "invalid.jpg"
            invalid.write_bytes(b"not an image")
            with self.assertRaisesRegex(ValueError, "Invalid image file"):
                workflow.add_source(project, invalid, "invalid-image")
            self.assertFalse((project / "escaped.jpg").exists())

    def test_validate_rejects_corrupt_duration_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 1)
            manifest_path = project / "project.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["defaults"]["duration_seconds"] = 3
            workflow.write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "at least 4 seconds"):
                workflow.validate(project)

    def test_migrates_schema_v3_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 1, 5)
            project_path = project / "project.json"
            shot_path = project / "shots/shot-01/shot.json"
            manifest = json.loads(project_path.read_text(encoding="utf-8"))
            shot = json.loads(shot_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = 3
            manifest["defaults"].pop("time_boundaries_seconds")
            manifest["workflow"] = {"mode": "staged_customer_review"}
            manifest["shots"][0].pop("review_mode")
            for key in ("review_mode", "review_mode_source", "review_mode_reason", "approvals"):
                shot.pop(key)
            shot["panels"] = [
                {
                    "position": position,
                    "time": "旧时间",
                    "label": f"动作{index}",
                    "description": "状态",
                    "image": f"panels/panel-{index:02d}.png",
                }
                for index, position in enumerate(workflow.POSITIONS, start=1)
            ]
            workflow.write_json(project_path, manifest)
            workflow.write_json(shot_path, shot)

            workflow.migrate(project)
            migrated = json.loads(project_path.read_text(encoding="utf-8"))
            migrated_shot = json.loads(shot_path.read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], 4)
            self.assertTrue((project / "project.json.bak").is_file())
            self.assertTrue((project / "shared-brief.md").is_file())
            self.assertIsNone(migrated["workflow"]["parallel_launch_mode"])
            self.assertIsNone(migrated["workflow"]["max_parallel_shot_tasks"])
            self.assertFalse(migrated["shots"][0]["task"]["active"])
            self.assertEqual(migrated_shot["panels"][0]["start_seconds"], 0)
            self.assertEqual(migrated_shot["panels"][-1]["end_seconds"], 5)
            workflow.validate(project)


if __name__ == "__main__":
    unittest.main()
