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


def prepare_content_plan(project: Path) -> None:
    manifest = workflow.read_json(project / "project.json")
    entries = []
    for index, shot in enumerate(manifest["shots"], start=1):
        entries.append({
            "shot_id": shot["id"], "context": f"场景{index}",
            "confirmation": f"确认第{index}张四格设计",
            "primary_selling_point": f"卖点{index}", "purpose": f"展示角度{index}",
            "panel_beats": [f"第{index}张第{panel}格" for panel in range(1, 5)],
            "shot_scales": ["wide", "medium", "close", "macro"],
            "opening_motif": f"开头{index}", "action_motif": f"动作{index}",
            "ending_motif": f"结尾{index}", "avoid_repeating": [],
            "intentional_bookend": False,
        })
    workflow.write_json(project / "content-plan.json", {
        "content_type": "showcase",
        "relationship": "single" if len(entries) == 1 else "independent",
        "approval_source": "user", "confirmation": "确认这批四格设计",
        "shots": entries,
    })
    for shot in manifest["shots"]:
        data = workflow.read_json(workflow.shot_json_path(project, shot["id"]))
        if not data.get("design_approvals"):
            confirm_design(project, shot["id"])


def confirm_design(project: Path, sid="shot-01") -> None:
    review_id = workflow.prepare_design_review(project, sid)
    workflow.approve_design(project, sid, review_id, "确认当前设计 / 明确快速请求的测试记录")


def prepare(project: Path, sid="shot-01") -> None:
    prepare_content_plan(project)
    manifest = workflow.read_json(project / "project.json")
    if not manifest.get("assets"):
        source = project / "input.png"
        make_image(source)
        workflow.add_source(project, source, "image-01")
    (project / "shared-brief.md").write_text("Approved wooden desk and daylight", encoding="utf-8")
    data = workflow.read_json(workflow.shot_json_path(project, sid))
    entry = next(item for item in workflow.read_json(project / "content-plan.json")["shots"] if item["shot_id"] == sid)
    boundaries = manifest["defaults"]["time_boundaries_seconds"]
    data.update(references=[{"id": "image-01", "roles": ["product_identity"]}], sequence_type="cuts",
                review_style="木桌自然光写实摄影", review_selling_point=entry["primary_selling_point"],
                review_context=entry["context"], review_purpose=entry["purpose"])
    data["panels"] = [dict(position=position, start_seconds=boundaries[i], end_seconds=boundaries[i+1],
                          time=f"{boundaries[i]}–{boundaries[i+1]}秒", label="外观展示", description=entry["panel_beats"][i],
                          plan_panel_id=f"{sid}:panel-{i + 1}", shot_scale=entry["shot_scales"][i])
                      for i, position in enumerate(workflow.POSITIONS)]
    workflow.write_json(workflow.shot_json_path(project, sid), data)
    prompt = f"四宫格9:16，产品以image-01为准。木桌自然光写实摄影。{data['review_selling_point']}。{data['review_context']}。{data['review_purpose']}。\n"
    prompt += "\n".join(f"{panel['time']} {panel['label']} {panel['description']} {workflow.SHOT_SCALE_LABELS[panel['shot_scale']]}" for panel in data["panels"])
    (project / "shots" / sid / "storyboard-prompt.md").write_text(prompt, encoding="utf-8")
    workflow.check_prompt_plan(project, sid, "主对话核对设计、景别和跨分镜动作")


def prepare_all(project: Path) -> None:
    """Prepare every staged shot before a new project's first launch choice."""
    for row in workflow.read_json(project / "project.json")["shots"]:
        sid = row["id"]
        data = workflow.read_json(workflow.shot_json_path(project, sid))
        if data["review_mode"] == "staged" and data["status"] == "todo":
            prepare(project, sid)
            workflow.set_status(project, sid, "storyboard_prompt_pending", coordinator=True)


def mark_legacy_handoff(project: Path) -> None:
    """Model a pre-handoff project whose existing launch behavior is preserved."""
    path = project / "project.json"
    manifest = workflow.read_json(path)
    manifest["workflow"].pop("handoff_model", None)
    workflow.write_json(path, manifest)


def approve_prompt(project: Path, sid="shot-01", confirmation="确认当前镜头与完整提示词") -> None:
    workflow.check_prompt_plan(project, sid, "主对话已核对当前提示词")
    review_id = workflow.prepare_prompt_review(project, sid)
    workflow.approve(project, sid, "storyboard_prompt", None, review_id, confirmation)


def approve_artifact(project: Path, sid: str, stage: str, note=None) -> None:
    # Read the previously submitted ID; never silently prepare a new review here.
    review = workflow.read_json(workflow.shot_json_path(project, sid))["artifact_review"]
    workflow.approve(project, sid, stage, note, review["id"], note or "确认当前展示的产物")


def record_image(project: Path, sid="shot-01", thread_id=None, host_id=None) -> None:
    workflow.preflight(project, sid, thread_id, host_id)
    path = workflow.shot_json_path(project, sid)
    data = workflow.read_json(path)
    Image.new("RGB", (90, 160), "blue").save(path.parent / f"storyboard-review-v{data['storyboard_version']:02d}.png")
    data["qa"] = {"result": "pass", "notes": []}
    workflow.write_json(path, data)


class WorkflowTests(unittest.TestCase):
    def test_new_multishot_requires_confirmed_content_plan_before_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 2)
            with self.assertRaisesRegex(ValueError, "Content plan needs"):
                workflow.set_concurrency(project, "all")
            prepare_content_plan(project)
            plan_path = project / "content-plan.json"
            plan = workflow.read_json(plan_path)
            plan["shots"][1]["opening_motif"] = plan["shots"][0]["opening_motif"]
            plan["shots"][1]["action_motif"] = plan["shots"][0]["action_motif"]
            plan["shots"][1]["ending_motif"] = plan["shots"][0]["ending_motif"]
            workflow.write_json(plan_path, plan)
            with self.assertRaisesRegex(ValueError, "repeats a complete action arc"):
                workflow.set_concurrency(project, "all")
            prepare_all(project)
            workflow.set_concurrency(project, "all")
            workflow.register_task(project, "shot-01", "thread-1", None)
            brief = workflow.task_brief(project, "shot-01")
            self.assertIn("content-plan.json", brief)

    def test_content_plan_scales_and_bookend_need_justification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo")
            prepare_content_plan(project)
            path = project / "content-plan.json"
            plan = workflow.read_json(path)
            plan["shots"][0]["shot_scales"] = ["close"] * 4
            workflow.write_json(path, plan)
            with self.assertRaisesRegex(ValueError, "three scales"):
                workflow.content_plan(project, workflow.read_json(project / "project.json"))
            plan["shots"][0]["scale_exception_reason"] = "微型产品，展示表面细节"
            plan["shots"][0]["ending_motif"] = plan["shots"][0]["opening_motif"]
            workflow.write_json(path, plan)
            with self.assertRaisesRegex(ValueError, "repeats its opening"):
                workflow.content_plan(project, workflow.read_json(project / "project.json"))
            plan["shots"][0]["intentional_bookend"] = True
            plan["shots"][0]["bookend_reason"] = "包装由封闭变为已打开"
            workflow.write_json(path, plan)
            confirm_design(project)
            workflow.content_plan(project, workflow.read_json(project / "project.json"))

    def test_explicit_skip_needs_fast_mode_and_old_projects_remain_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 2)
            prepare_content_plan(project)
            plan_path = project / "content-plan.json"
            plan = workflow.read_json(plan_path)
            plan["approval_source"] = "explicit_fast_request"
            plan["confirmation"] = "直接生成"
            for shot in plan["shots"]:
                shot["confirmation"] = "直接生成"
            workflow.write_json(plan_path, plan)
            with self.assertRaisesRegex(ValueError, "Explicit skip requires fast"):
                workflow.content_plan(project, workflow.read_json(project / "project.json"))
            for sid in ("shot-01", "shot-02"):
                workflow.set_review_mode(project, sid, "fast", "直接生成")
                confirm_design(project, sid)
            workflow.content_plan(project, workflow.read_json(project / "project.json"))
            workflow.set_review_mode(project, "shot-01", "staged", "单独审核这一张")
            plan["shots"][0]["approval_source"] = "user"
            plan["shots"][0]["confirmation"] = "确认第一张新设计"
            workflow.write_json(plan_path, plan)
            confirm_design(project, "shot-01")
            workflow.content_plan(project, workflow.read_json(project / "project.json"))

            old_project = Path(directory) / "old-project"
            workflow.init_project(old_project, "old", 2)
            manifest = workflow.read_json(old_project / "project.json")
            manifest["workflow"].pop("content_plan_required")
            manifest["workflow"].pop("handoff_model")
            workflow.write_json(old_project / "project.json", manifest)
            (old_project / "content-plan.json").unlink()
            workflow.set_concurrency(old_project, "all")
            workflow.register_task(old_project, "shot-01", "old-task", None)

    def test_revising_one_content_assignment_stales_only_its_prompt_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 2)
            for sid in ("shot-01", "shot-02"):
                prepare(project, sid)
                workflow.set_status(project, sid, "storyboard_prompt_pending", coordinator=True)
            workflow.set_concurrency(project, "all")
            for sid in ("shot-01", "shot-02"):
                workflow.register_task(project, sid, f"task-{sid}", None)
                approve_prompt(project, sid)
            plan_path = project / "content-plan.json"
            plan = workflow.read_json(plan_path)
            plan["shots"][0]["purpose"] = "新的展示目的"
            workflow.write_json(plan_path, plan)
            with self.assertRaisesRegex(ValueError, "stale"):
                workflow.preflight(project, "shot-01", "task-shot-01")
            workflow.preflight(project, "shot-02", "task-shot-02")

    def test_prompt_review_requires_current_packet_and_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo")
            prepare(project)
            workflow.set_status(project, "shot-01", "storyboard_prompt_pending", coordinator=True)
            with self.assertRaisesRegex(ValueError, "requires current --review-id"):
                workflow.approve(project, "shot-01", "storyboard_prompt", None)
            review_id = workflow.prepare_prompt_review(project, "shot-01")
            summary = workflow.prompt_review_summary(workflow.read_json(workflow.shot_json_path(project, "shot-01")))
            self.assertEqual(summary["visual_style"], "木桌自然光写实摄影")
            self.assertEqual(len(summary["panels"]), 4)
            with self.assertRaisesRegex(ValueError, "explicit --confirmation"):
                workflow.approve(project, "shot-01", "storyboard_prompt", None, review_id, " ")
            with self.assertRaisesRegex(ValueError, "stale prompt review"):
                workflow.approve(project, "shot-01", "storyboard_prompt", None, "wrong-id", "确认")
            workflow.approve(project, "shot-01", "storyboard_prompt", None, review_id, "确认本镜头当前方案及提示词")
            workflow.preflight(project, "shot-01")

    def test_prompt_review_rejects_mismatch_and_stale_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo")
            prepare(project)
            workflow.set_status(project, "shot-01", "storyboard_prompt_pending", coordinator=True)
            path = project / "shots/shot-01/storyboard-prompt.md"
            original = path.read_text(encoding="utf-8")
            path.write_text(original.replace("第1张第1格", "产品在空中"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs from shot review summary"):
                workflow.prepare_prompt_review(project, "shot-01")
            path.write_text(original, encoding="utf-8")
            review_id = workflow.prepare_prompt_review(project, "shot-01")
            path.write_text(original + "\n新要求", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale prompt review"):
                workflow.approve(project, "shot-01", "storyboard_prompt", None, review_id, "确认")
            path.write_text(original, encoding="utf-8")
            data_path = workflow.shot_json_path(project, "shot-01")
            data = workflow.read_json(data_path)
            data["review_style"] = "另一种风格"
            workflow.write_json(data_path, data)
            with self.assertRaisesRegex(ValueError, "stale prompt review"):
                workflow.approve(project, "shot-01", "storyboard_prompt", None, review_id, "确认")

    def test_legacy_approval_without_review_record_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo")
            prepare(project)
            workflow.set_status(project, "shot-01", "storyboard_prompt_pending", coordinator=True)
            approve_prompt(project)
            path = workflow.shot_json_path(project, "shot-01")
            data = workflow.read_json(path)
            data["approvals"][-1].pop("prompt_review_id")
            data["approvals"][-1].pop("confirmation")
            data.pop("prompt_review")
            workflow.write_json(path, data)
            workflow.preflight(project, "shot-01")

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
            prepare_all(project)
            workflow.set_concurrency(project, "pilot", 1)
            workflow.register_task(project, "shot-01", "thread-123", "host-456")
            approve_prompt(project)
            record_image(project, thread_id="thread-123", host_id="host-456")
            workflow.set_status(project, "shot-01", "storyboard_review_pending", coordinator=True)
            approve_artifact(project, "shot-01", "storyboard", "画面通过")
            (project / "shots/shot-01/video-prompt.md").write_text("Approved video guidance", encoding="utf-8")
            workflow.set_status(project, "shot-01", "video_prompt_review_pending", coordinator=True)
            approve_artifact(project, "shot-01", "video_prompt", None)
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
                hashlib.sha256((project / "sources/image-01.png").read_bytes()).hexdigest(),
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
            (project / "shots/shot-01/video-prompt.md").write_text("匹配已确认设计的视频提示词", encoding="utf-8")
            workflow.set_status(project, "shot-01", "review_pending", coordinator=True)
            approve_artifact(project, "shot-01", "review_package", "完整审核包通过")
            workflow.validate(project)

            shot = json.loads((project / "shots/shot-01/shot.json").read_text(encoding="utf-8"))
            self.assertEqual(shot["review_mode"], "fast")
            self.assertEqual(shot["review_mode_source"], "explicit_user_request")
            self.assertEqual(shot["status"], "complete")

    def test_rejects_short_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "at least 4 seconds"):
                workflow.init_project(Path(directory) / "project", "demo", 1, 3)

    def test_prepared_concurrency_requires_user_choice_and_supports_pilot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 3)
            manifest = json.loads((project / "project.json").read_text(encoding="utf-8"))
            manifest["workflow"]["handoff_model"] = workflow.PREPARED_PROMPT_HANDOFF
            workflow.write_json(project / "project.json", manifest)
            self.assertTrue((project / "shared-brief.md").is_file())
            self.assertIsNone(manifest["workflow"]["parallel_launch_mode"])
            self.assertIsNone(manifest["workflow"]["max_parallel_shot_tasks"])
            self.assertEqual(manifest["workflow"]["video_prompt_owner"], "current_conversation")

            with self.assertRaisesRegex(ValueError, "Concurrency choice is not recorded"):
                workflow.register_task(project, "shot-01", "thread-1", None)

            prepare_all(project)
            workflow.set_concurrency(project, "pilot", 2)
            workflow.register_task(project, "shot-01", "thread-1", None)
            workflow.register_task(project, "shot-02", "thread-2", None)
            with self.assertRaisesRegex(ValueError, "No shot-task slot available"):
                workflow.register_task(project, "shot-03", "thread-3", None)

            board = workflow.dashboard(project)
            brief = workflow.task_brief(project, "shot-01")
            self.assertIn("shot-01", board)
            self.assertIn("创意设计待确认", board)
            self.assertIn(str((project / "shared-brief.md").resolve()), brief)
            self.assertIn("不要重新解释或复制全局规则", brief)
            self.assertIn("不要自动重试", brief)

            workflow.release_task(project, "shot-01")
            with self.assertRaisesRegex(ValueError, "Pilot scope exhausted"):
                workflow.register_task(project, "shot-03", "thread-3", None)
            workflow.release_task(project, "shot-02")
            workflow.set_concurrency(project, "all", reason="用户看过试做后要求全部继续")
            workflow.register_task(project, "shot-03", "thread-3", None)
            workflow.validate(project)

    def test_all_shots_concurrency_uses_project_shot_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            workflow.init_project(project, "demo", 3)
            prepare_all(project)
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
            approve_prompt(project)
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
            self.assertNotIn("handoff_model", migrated["workflow"])
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
