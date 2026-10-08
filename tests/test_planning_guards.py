from __future__ import annotations

import contextlib
import copy
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_workflow import workflow as w, prepare, prepare_all, prepare_content_plan, confirm_design, approve_prompt, record_image, approve_artifact, mark_legacy_handoff


class PlanningGuardTests(unittest.TestCase):
    def setUp(self):
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        w.init_project(self.root, "planning", 2)
        prepare_content_plan(self.root)

    def plan(self):
        return w.read_json(self.root / "content-plan.json")

    def save_plan(self, plan):
        w.write_json(self.root / "content-plan.json", plan)

    def test_changed_creative_design_cannot_reuse_confirmation_or_review_id(self):
        mark_legacy_handoff(self.root)
        w.set_concurrency(self.root, "all")
        old_id = w.read_json(w.shot_json_path(self.root, "shot-01"))["design_review"]["id"]
        plan = self.plan()
        plan["shots"][0]["context"] = "新的送礼场景"
        plan["shots"][0]["panel_beats"] = [f"全新画面{i}" for i in range(4)]
        self.save_plan(plan)
        with self.assertRaisesRegex(ValueError, "stale creative review"):
            w.approve_design(self.root, "shot-01", old_id, "旧回复")
        with self.assertRaisesRegex(ValueError, "stale creative approval"):
            w.register_task(self.root, "shot-01", "task-1", None)
        confirm_design(self.root)
        w.register_task(self.root, "shot-01", "task-1", None)
        records = w.read_json(w.shot_json_path(self.root, "shot-01"))["design_approvals"]
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]["binding"], records[1]["binding"])

    def test_confirmation_text_alone_is_not_an_approval(self):
        path = w.shot_json_path(self.root, "shot-01")
        data = w.read_json(path)
        data.pop("design_approvals")
        w.write_json(path, data)
        with self.assertRaisesRegex(ValueError, "Missing or stale creative approval"):
            w.set_concurrency(self.root, "all")

    def test_prepare_then_modify_then_approve_is_rejected(self):
        review_id = w.prepare_design_review(self.root, "shot-01")
        plan = self.plan()
        plan["shots"][0]["shot_scales"].reverse()
        self.save_plan(plan)
        with self.assertRaisesRegex(ValueError, "stale creative review"):
            w.approve_design(self.root, "shot-01", review_id, "确认旧顺序")

    def test_other_incomplete_draft_does_not_block_current_shot(self):
        # Legacy launches are allowed to hand off one prepared shot at a time.
        mark_legacy_handoff(self.root)
        prepare(self.root, "shot-02")
        w.set_concurrency(self.root, "all")
        w.set_status(self.root, "shot-02", "storyboard_prompt_pending", True)
        approve_prompt(self.root, "shot-02")
        plan = self.plan()
        plan["shots"][0]["panel_beats"] = []
        self.save_plan(plan)
        w.register_task(self.root, "shot-02", "task-2", None)
        w.preflight(self.root, "shot-02", "task-2")
        w.validate(self.root)
        with self.assertRaisesRegex(ValueError, "four panel beats"):
            w.task_brief(self.root, "shot-01")

    def test_global_design_change_stales_both_shots(self):
        plan = self.plan()
        plan["content_type"] = "mixed"
        self.save_plan(plan)
        for sid in ("shot-01", "shot-02"):
            with self.subTest(sid=sid), self.assertRaisesRegex(ValueError, "stale creative approval"):
                w.content_plan(self.root, w.read_json(self.root / "project.json"), sid)

    def test_prompt_drift_is_rejected_even_when_prompt_matches_local_shot(self):
        prepare(self.root)
        path = w.shot_json_path(self.root, "shot-01")
        original = w.read_json(path)
        mutations = (lambda d: d.update(review_context="礼盒开箱"),
                     lambda d: d.update(review_selling_point="另一个卖点"),
                     lambda d: d.update(review_purpose="另一个目的"),
                     lambda d: d["panels"][0].update(description="重复摆拍"),
                     lambda d: d["panels"][0].update(shot_scale="macro"),
                     lambda d: d["panels"][0].update(plan_panel_id="shot-02:panel-1"))
        for index, mutate in enumerate(mutations):
            data = copy.deepcopy(original)
            mutate(data)
            w.write_json(path, data)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "differs from approved design"):
                w.check_prompt_plan(self.root, "shot-01", "核对")

    def test_new_prompt_requires_new_coordinator_check(self):
        prepare(self.root)
        w.set_status(self.root, "shot-01", "storyboard_prompt_pending", True)
        prepare_all(self.root)
        w.set_concurrency(self.root, "all")
        w.register_task(self.root, "shot-01", "review-task", None)
        prompt = self.root / "shots/shot-01/storyboard-prompt.md"
        prompt.write_text(prompt.read_text(encoding="utf-8") + "\n额外摄影细节", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale plan check"):
            w.prepare_prompt_review(self.root, "shot-01")
        w.check_prompt_plan(self.root, "shot-01", "新的摄影细节与方案一致")
        w.prepare_prompt_review(self.root, "shot-01")

    def test_fast_generation_cannot_skip_coordinator_check(self):
        prepare(self.root)
        path = w.shot_json_path(self.root, "shot-01")
        data = w.read_json(path)
        data.pop("plan_check")
        w.write_json(path, data)
        w.set_review_mode(self.root, "shot-01", "fast", "直接生成")
        with self.assertRaisesRegex(ValueError, "plan check"):
            w.set_status(self.root, "shot-01", "running", True)
        w.check_prompt_plan(self.root, "shot-01", "快速模式内部核对")
        w.set_status(self.root, "shot-01", "running", True)
        w.preflight(self.root, "shot-01")

    def test_all_fast_rejects_concurrency_and_registration(self):
        for sid in ("shot-01", "shot-02"):
            w.set_review_mode(self.root, sid, "fast", "直接生成")
        with self.assertRaisesRegex(ValueError, "Fast-mode"):
            w.set_concurrency(self.root, "all")
        with self.assertRaisesRegex(ValueError, "Fast-mode"):
            w.register_task(self.root, "shot-01", "fast-task", None)

    def test_mixed_modes_only_register_staged_and_active_switch_requires_release(self):
        w.set_review_mode(self.root, "shot-02", "fast", "第二张直接生成")
        prepare_all(self.root)
        w.set_concurrency(self.root, "all")
        w.register_task(self.root, "shot-01", "staged-task", None)
        with self.assertRaisesRegex(ValueError, "Fast-mode"):
            w.register_task(self.root, "shot-02", "fast-task", None)
        with self.assertRaisesRegex(ValueError, "Release"):
            w.set_review_mode(self.root, "shot-01", "fast", "第一张也直接生成")
        w.release_task(self.root, "shot-01")
        w.set_review_mode(self.root, "shot-01", "fast", "第一张也直接生成")
        w.validate(self.root)

    def test_validation_rejects_forged_active_fast_task(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "all")
        w.set_review_mode(self.root, "shot-01", "fast", "直接生成")
        project = w.read_json(self.root / "project.json")
        project["shots"][0]["task"] = {"thread_id": "bad", "active": True}
        w.write_json(self.root / "project.json", project)
        with self.assertRaisesRegex(ValueError, "Fast-mode"):
            w.validate(self.root)

    def test_wait_failure_complete_and_video_briefs_do_not_assign_prompt_writing(self):
        # These states are synthetic: this test targets instruction routing, not approvals.
        mark_legacy_handoff(self.root)
        path = w.shot_json_path(self.root, "shot-01")
        for status in ("storyboard_review_pending", "review_pending", "generation_failed", "failed",
                       "complete", "video_prompt_pending", "video_prompt_review_pending", "storyboard_generating"):
            data = w.read_json(path)
            data["status"] = status
            w.write_json(path, data)
            with self.subTest(status=status):
                brief = w.task_brief(self.root, "shot-01")
                self.assertNotIn("按已确认的四格画面与景别写技术提示词", brief)
                self.assertNotIn("缺失先按模板保存", brief)

    def test_exception_fields_require_real_boolean_and_nonempty_text(self):
        original = self.plan()
        cases = (("intentional_bookend", "false"), ("intentional_bookend", 1),
                 ("bookend_reason", 123), ("bookend_reason", []), ("bookend_reason", " "),
                 ("scale_exception_reason", 123), ("scale_exception_reason", True))
        for key, value in cases:
            plan = copy.deepcopy(original)
            plan["shots"][0][key] = value
            self.save_plan(plan)
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "boolean|nonempty text"):
                w.content_plan(self.root, w.read_json(self.root / "project.json"), "shot-01", False)

    def test_design_approval_write_failure_rolls_back_history_and_plan(self):
        review_id = w.prepare_design_review(self.root, "shot-01")
        path = w.shot_json_path(self.root, "shot-01")
        before = path.read_bytes()
        old_plan = (self.root / "content-plan.json").read_bytes()
        writer = w.write_json
        def fail_plan(path, data):
            if path.name == "content-plan.json":
                raise OSError("simulated disk failure")
            writer(path, data)
        with patch.object(w, "write_json", side_effect=fail_plan), self.assertRaises(OSError):
            w.approve_design(self.root, "shot-01", review_id, "确认")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((self.root / "content-plan.json").read_bytes(), old_plan)

    def test_cli_design_and_prompt_check_commands(self):
        prepare(self.root)
        command = [sys.executable, "-X", "utf8", str(Path(w.__file__))]
        result = subprocess.run(command + ["prepare-design-review", str(self.root), "shot-01"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        review_id = w.read_json(w.shot_json_path(self.root, "shot-01"))["design_review"]["id"]
        for arguments in (["approve-design", str(self.root), "shot-01", "--review-id", review_id, "--confirmation", "确认"],
                          ["check-prompt-plan", str(self.root), "shot-01", "--note", "已核对"]):
            result = subprocess.run(command + arguments, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_fast_skip_binds_design_without_staged_prompt_approval(self):
        prepare(self.root)
        w.set_review_mode(self.root, "shot-01", "fast", "无需审核，直接生成")
        plan = self.plan()
        plan["shots"][0]["approval_source"] = "explicit_fast_request"
        self.save_plan(plan)
        review_id = w.prepare_design_review(self.root, "shot-01")
        w.approve_design(self.root, "shot-01", review_id, "无需审核，直接生成")
        w.check_prompt_plan(self.root, "shot-01", "内部核对完成")
        w.set_status(self.root, "shot-01", "running", True)
        record_image(self.root)
        (self.root / "shots/shot-01/video-prompt.md").write_text("匹配分镜的视频提示词草稿", encoding="utf-8")
        w.set_status(self.root, "shot-01", "review_pending", True)
        approve_artifact(self.root, "shot-01", "review_package", "用户批准审核包")
        data = w.read_json(w.shot_json_path(self.root, "shot-01"))
        self.assertEqual([a["stage"] for a in data["approvals"]], ["review_package"])
        self.assertEqual(data["status"], "complete")
        w.validate(self.root)

    def test_legacy_project_does_not_require_new_records_or_panel_ids(self):
        prepare(self.root)
        project = w.read_json(self.root / "project.json")
        project["workflow"].pop("content_plan_required")
        project["workflow"].pop("handoff_model")
        w.write_json(self.root / "project.json", project)
        path = w.shot_json_path(self.root, "shot-01")
        data = w.read_json(path)
        for key in ("design_review", "design_approvals", "plan_check", "review_context", "review_purpose"):
            data.pop(key, None)
        for panel in data["panels"]:
            panel.pop("plan_panel_id")
            panel.pop("shot_scale")
        w.write_json(path, data)
        w.set_status(self.root, "shot-01", "storyboard_prompt_pending", True)
        review_id = w.prepare_prompt_review(self.root, "shot-01")
        w.approve(self.root, "shot-01", "storyboard_prompt", None, review_id, "确认")
        w.set_concurrency(self.root, "all")
        w.register_task(self.root, "shot-01", "legacy-task", None)
        w.preflight(self.root, "shot-01", "legacy-task")

    def test_image_still_requires_visual_qa(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "all")
        w.register_task(self.root, "shot-01", "qa-task", None)
        approve_prompt(self.root)
        record_image(self.root, thread_id="qa-task")
        path = w.shot_json_path(self.root, "shot-01")
        data = w.read_json(path)
        data["qa"] = {"result": "not_run", "notes": []}
        w.write_json(path, data)
        with self.assertRaisesRegex(ValueError, "visual QA"):
            w.set_status(self.root, "shot-01", "storyboard_review_pending", True)

    def test_duplicate_arc_introduced_between_prepare_and_approval_is_rejected(self):
        plan = self.plan()
        keys = ("opening_motif", "action_motif", "ending_motif")
        for entry in plan["shots"]:
            entry.update({key: f"全新的{key}" for key in keys})
        self.save_plan(plan)
        ids = {sid: w.prepare_design_review(self.root, sid) for sid in ("shot-01", "shot-02")}
        w.approve_design(self.root, "shot-01", ids["shot-01"], "确认")
        with self.assertRaisesRegex(ValueError, "repeats a complete action arc"):
            w.approve_design(self.root, "shot-02", ids["shot-02"], "确认")


if __name__ == "__main__":
    unittest.main()
