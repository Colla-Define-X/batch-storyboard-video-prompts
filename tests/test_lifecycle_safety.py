from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from test_workflow import workflow as w, prepare, prepare_all, mark_legacy_handoff, approve_prompt, approve_artifact, record_image


class LifecycleSafetyTests(unittest.TestCase):
    def setUp(self):
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        w.init_project(self.root, "audit")

    def save(self, relative, value, root=None):
        root = root or self.root
        revision = w.content_revision(root, relative)
        draft = self.base / "owner-draft.txt"
        draft.write_text(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value, encoding="utf-8")
        return w.save_content(root, relative, draft, revision)

    def data(self, root=None, sid="shot-01"):
        return w.read_json(w.shot_json_path(root or self.root, sid))

    def ready(self, root=None, sid="shot-01", fast=False):
        root = root or self.root
        prepare(root, sid)
        if fast:
            w.set_review_mode(root, sid, "fast", "用户明确直接生成")
            w.set_status(root, sid, "running", True)
        else:
            w.set_status(root, sid, "storyboard_prompt_pending", True)
            approve_prompt(root, sid)

    def image_review(self, fast=False):
        self.ready(fast=fast)
        record_image(self.root)
        if fast:
            self.save("shots/shot-01/video-prompt.md", "Video A")
        w.set_status(self.root, "shot-01", "review_pending" if fast else "storyboard_review_pending", True)
        return self.data()["artifact_review"]["id"]

    def video_review(self):
        self.image_review()
        approve_artifact(self.root, "shot-01", "storyboard", "图片可用")
        self.save("shots/shot-01/video-prompt.md", "Video A")
        w.set_status(self.root, "shot-01", "video_prompt_review_pending", True)
        return self.data()["artifact_review"]["id"]

    def test_inflight_revision_cannot_reset_a_claim_in_either_mode(self):
        for fast in (False, True):
            root = self.base / f"inflight-{fast}"
            w.init_project(root, "inflight")
            self.ready(root, fast=fast)
            w.preflight(root, "shot-01")
            before = w.shot_json_path(root, "shot-01").read_bytes()
            for stage in ("storyboard_prompt", "storyboard", "video_prompt"):
                with self.subTest(fast=fast, stage=stage), self.assertRaisesRegex(ValueError, "Wait for the claimed"):
                    w.revise(root, "shot-01", stage, "用户想调整")
            with self.assertRaisesRegex(ValueError, "Wait for the claimed"):
                w.revise_designs(root, ["shot-01"], "用户修改设计")
            self.assertEqual(w.shot_json_path(root, "shot-01").read_bytes(), before)

    def test_stale_inputs_allow_actual_failure_but_not_unapproved_retry(self):
        self.ready()
        w.preflight(self.root, "shot-01")
        original_binding = self.data()["generation_binding"]
        self.save("shared-brief.md", "用户更新了共享摄影要求")
        w.set_status(self.root, "shot-01", "generation_failed", True)
        w.validate(self.root)
        self.assertEqual(self.data()["generation_binding"], original_binding)
        with self.assertRaisesRegex(ValueError, "stale"):
            w.retry_shot(self.root, "shot-01", "storyboard_generating", "用户要求重试")
        w.revise(self.root, "shot-01", "storyboard_prompt", "按新要求修订")
        approve_prompt(self.root)
        w.preflight(self.root, "shot-01")
        self.assertEqual(self.data()["storyboard_version"], 2)

    def test_missing_source_does_not_prevent_recording_failure(self):
        self.ready()
        w.preflight(self.root, "shot-01")
        (self.root / "sources/image-01.png").unlink()
        w.set_status(self.root, "shot-01", "generation_failed", True)
        self.assertEqual(self.data()["failed_from"], "storyboard_generating")
        with self.assertRaises(FileNotFoundError):
            w.retry_shot(self.root, "shot-01", "storyboard_generating", "重试")

    def test_video_failure_preserves_phase_and_cannot_retry_image(self):
        self.image_review()
        approve_artifact(self.root, "shot-01", "storyboard")
        self.save("shared-brief.md", "改动后的共享说明")
        w.set_status(self.root, "shot-01", "generation_failed", True)
        self.assertEqual(self.data()["failed_from"], "video_prompt_pending")
        with self.assertRaisesRegex(ValueError, "Invalid staged retry"):
            w.retry_shot(self.root, "shot-01", "storyboard_generating", "重试")
        with self.assertRaisesRegex(ValueError, "stale"):
            w.retry_shot(self.root, "shot-01", "video_prompt_pending", "重试视频文案")

    def test_finished_fast_image_can_revise_video_while_still_running(self):
        self.ready(fast=True)
        record_image(self.root)
        image = self.root / "shots/shot-01/storyboard-review-v01.png"
        before = image.read_bytes()
        w.revise(self.root, "shot-01", "video_prompt", "用户想调整文案")
        self.save("shots/shot-01/video-prompt.md", "新版文案")
        w.prepare_artifact_review(self.root, "shot-01")
        approve_artifact(self.root, "shot-01", "review_package")
        w.validate(self.root)
        self.assertEqual(image.read_bytes(), before)
        self.assertEqual(self.data()["storyboard_version"], 1)

    def test_finished_image_can_be_redone_without_confusing_claim_with_inflight(self):
        self.ready()
        record_image(self.root)
        w.revise(self.root, "shot-01", "storyboard", "用户重新生成")
        w.preflight(self.root, "shot-01")
        self.assertEqual(self.data()["storyboard_version"], 2)

    def test_image_approval_requires_submitted_id_and_confirmation(self):
        review_id = self.image_review()
        for supplied, reply in ((None, "确认"), (review_id, " "), ("old-id", "确认")):
            with self.subTest(supplied=supplied), self.assertRaises(ValueError):
                w.approve(self.root, "shot-01", "storyboard", None, supplied, reply)
        self.assertEqual(self.data()["status"], "storyboard_review_pending")

    def test_changed_review_image_cannot_use_old_approval(self):
        review_id = self.image_review()
        Image.new("RGB", (90, 160), "red").save(self.root / "shots/shot-01/storyboard-review-v01.png")
        with self.assertRaisesRegex(ValueError, "stale artifact review"):
            w.approve(self.root, "shot-01", "storyboard", None, review_id, "确认旧图")
        self.assertFalse((self.root / "shots/shot-01/storyboard-final.png").exists())

    def test_video_save_invalidates_review_and_requires_fresh_reply(self):
        old_id = self.video_review()
        self.save("shots/shot-01/video-prompt.md", "Video B")
        self.assertNotIn("artifact_review", self.data())
        with self.assertRaisesRegex(ValueError, "stale artifact review"):
            w.approve(self.root, "shot-01", "video_prompt", None, old_id, "确认 A")
        new_id = w.prepare_artifact_review(self.root, "shot-01")
        self.assertNotEqual(new_id, old_id)
        with self.assertRaisesRegex(ValueError, "stale artifact review"):
            w.approve(self.root, "shot-01", "video_prompt", None, old_id, "旧回复")
        w.approve(self.root, "shot-01", "video_prompt", None, new_id, "确认 B")
        w.validate(self.root)

    def test_fast_video_revision_preserves_image_and_invalidates_package_review(self):
        old_id = self.image_review(fast=True)
        approve_artifact(self.root, "shot-01", "review_package")
        image = self.root / "shots/shot-01/storyboard-final.png"
        before = image.read_bytes()
        w.revise(self.root, "shot-01", "video_prompt", "只改文案")
        self.save("shots/shot-01/video-prompt.md", "Video B")
        with self.assertRaisesRegex(ValueError, "stale artifact review"):
            w.approve(self.root, "shot-01", "review_package", None, old_id, "确认旧版")
        w.prepare_artifact_review(self.root, "shot-01")
        approve_artifact(self.root, "shot-01", "review_package")
        w.validate(self.root)
        self.assertEqual(image.read_bytes(), before)
        self.assertEqual(self.data()["storyboard_version"], 1)

    def test_qa_change_invalidates_submitted_review(self):
        old_id = self.image_review()
        data = self.data()
        data["qa"]["notes"] = ["新增偏差"]
        self.save("shots/shot-01/shot.json", {"qa": data["qa"]})
        with self.assertRaisesRegex(ValueError, "stale artifact review"):
            w.approve(self.root, "shot-01", "storyboard", None, old_id, "确认旧 QA")

    def test_review_resubmission_uses_new_id_even_if_bytes_are_identical(self):
        old_id = self.video_review()
        new_id = w.prepare_artifact_review(self.root, "shot-01")
        self.assertNotEqual(old_id, new_id)
        with self.assertRaisesRegex(ValueError, "stale artifact review"):
            w.approve(self.root, "shot-01", "video_prompt", None, old_id, "旧轮次确认")

    def test_brief_distinguishes_current_and_invalidated_artifact_review(self):
        self.video_review()
        self.assertIn("当前产物审核记录有效", w.task_brief(self.root, "shot-01"))
        self.save("shots/shot-01/video-prompt.md", "Video B")
        brief = w.task_brief(self.root, "shot-01")
        self.assertIn("审核缺失或已过期", brief)
        self.assertIn("prepare-artifact-review", brief)
        self.assertNotIn("按已确认的四格画面与景别写技术提示词", brief)

    def test_legacy_completed_approval_is_readable_but_pending_needs_new_review(self):
        self.video_review()
        approve_artifact(self.root, "shot-01", "video_prompt")
        data = self.data()
        data.pop("artifact_review")
        for approval in data["approvals"]:
            if approval.pop("artifact_review_id", None):
                approval.pop("confirmation")
        w.write_json(w.shot_json_path(self.root, "shot-01"), data)
        w.validate(self.root)
        w.revise(self.root, "shot-01", "video_prompt", "修改旧项目文案")
        self.save("shots/shot-01/video-prompt.md", "New text")
        w.set_status(self.root, "shot-01", "video_prompt_review_pending", True)
        data = self.data()
        data.pop("artifact_review")  # An old project paused before versioned review existed.
        w.write_json(w.shot_json_path(self.root, "shot-01"), data)
        with self.assertRaisesRegex(ValueError, "stale artifact review"):
            w.approve(self.root, "shot-01", "video_prompt", None, "legacy", "旧回复")
        w.prepare_artifact_review(self.root, "shot-01")
        approve_artifact(self.root, "shot-01", "video_prompt")
        w.validate(self.root)

    def test_pilot_is_checked_at_preflight_without_registering_other_shot(self):
        root = self.base / "pilot"
        w.init_project(root, "pilot", 2)
        # This exercise starts from an older approved-prompt project.
        mark_legacy_handoff(root)
        self.ready(root, "shot-01")
        self.ready(root, "shot-02")
        with self.assertRaisesRegex(ValueError, "concurrency choice"):
            w.preflight(root, "shot-01")
        w.set_concurrency(root, "pilot", 1)
        w.register_task(root, "shot-01", "pilot-task", None)
        with self.assertRaisesRegex(ValueError, "outside the authorized pilot"):
            w.preflight(root, "shot-02")
        w.release_task(root, "shot-01")
        with self.assertRaisesRegex(ValueError, "active shot task"):
            w.preflight(root, "shot-01")
        w.register_task(root, "shot-01", "same-shot", None)
        w.preflight(root, "shot-01", "same-shot")
        self.assertTrue(self.data(root)["generation_claimed"])
        self.assertFalse(self.data(root, "shot-02").get("generation_claimed"))

    def test_new_pilot_round_does_not_invalidate_old_image_or_video_stage(self):
        root = self.base / "rounds"
        w.init_project(root, "rounds", 2)
        prepare_all(root)
        w.set_concurrency(root, "pilot", 1)
        w.register_task(root, "shot-01", "first", None)
        approve_prompt(root)
        record_image(root, thread_id="first")
        w.set_status(root, "shot-01", "storyboard_review_pending", True)
        approve_artifact(root, "shot-01", "storyboard")
        w.set_concurrency(root, "pilot", 1, reason="用户明确再试第二张")
        w.register_task(root, "shot-02", "second", None)
        self.save("shots/shot-01/video-prompt.md", "Video after task release", root)
        w.set_status(root, "shot-01", "video_prompt_review_pending", True)
        approve_artifact(root, "shot-01", "video_prompt")
        w.validate(root)

    def test_fast_shot_in_mixed_project_does_not_need_pilot_slot(self):
        root = self.base / "mixed"
        w.init_project(root, "mixed", 2)
        w.set_review_mode(root, "shot-02", "fast", "用户明确直接生成")
        prepare_all(root)
        w.set_concurrency(root, "pilot", 1)
        w.register_task(root, "shot-01", "staged", None)
        approve_prompt(root)
        self.ready(root, "shot-02", fast=True)
        w.preflight(root, "shot-02")
        w.preflight(root, "shot-01", "staged")
        w.validate(root)

    def test_scope_can_change_before_review_but_cannot_change_afterwards(self):
        self.save("project.json", {"delivery_scope": "storyboard_only"})
        self.ready()
        before = (self.root / "project.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "scope is locked"):
            self.save("project.json", {"delivery_scope": "storyboard_and_video_prompt", "name": "also changed"})
        self.assertEqual((self.root / "project.json").read_bytes(), before)
        w.revise(self.root, "shot-01", "storyboard_prompt", "返回修改提示词")
        with self.assertRaisesRegex(ValueError, "scope is locked"):
            self.save("project.json", {"delivery_scope": "storyboard_and_video_prompt"})
        self.save("project.json", {"name": "允许改名称", "delivery_scope": "storyboard_only"})

    def test_scope_rejection_preserves_approved_image_and_bindings(self):
        self.image_review()
        approve_artifact(self.root, "shot-01", "storyboard")
        before = self.data()
        image = (self.root / "shots/shot-01/storyboard-final.png").read_bytes()
        with self.assertRaisesRegex(ValueError, "scope is locked"):
            self.save("project.json", {"delivery_scope": "storyboard_only"})
        self.assertEqual(self.data(), before)
        self.assertEqual((self.root / "shots/shot-01/storyboard-final.png").read_bytes(), image)
        w.validate(self.root)

    def test_video_save_failure_rolls_back_text_and_review_together(self):
        self.video_review()
        path = w.shot_json_path(self.root, "shot-01")
        before = path.read_bytes()
        with patch.object(w, "write_json", side_effect=OSError("disk failure")), self.assertRaises(OSError):
            self.save("shots/shot-01/video-prompt.md", "Video B")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual((path.parent / "video-prompt.md").read_text(encoding="utf-8"), "Video A")

    def test_review_submission_failure_rolls_back_status_and_snapshot(self):
        self.ready()
        record_image(self.root)
        path = w.shot_json_path(self.root, "shot-01")
        before = path.read_bytes()
        writer = w.write_json
        def fail_project(target, data):
            if target == self.root / "project.json":
                raise OSError("summary failure")
            writer(target, data)
        with patch.object(w, "write_json", side_effect=fail_project), self.assertRaises(OSError):
            w.set_status(self.root, "shot-01", "storyboard_review_pending", True)
        self.assertEqual(path.read_bytes(), before)

    def test_artifact_review_cli_requires_and_accepts_current_review(self):
        self.video_review()
        command = [sys.executable, "-X", "utf8", str(Path(w.__file__))]
        result = subprocess.run(command + ["prepare-artifact-review", str(self.root), "shot-01"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = command + ["approve", str(self.root), "shot-01", "video_prompt"]
        self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
        result = subprocess.run(args + ["--review-id", self.data()["artifact_review"]["id"], "--confirmation", "确认新版"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_public_content_save_lifecycle_all_modes_and_scopes(self):
        # Unlike the unit fixtures, all editable project content uses the public
        # locked save protocol here. Only simulated image-tool outputs are direct.
        for fast in (False, True):
            for scope in ("storyboard_only", "storyboard_and_video_prompt"):
                with self.subTest(fast=fast, scope=scope):
                    root = self.base / f"public-{fast}-{scope}"
                    w.init_project(root, "public", delivery=scope)
                    if fast:
                        w.set_review_mode(root, "shot-01", "fast", "直接生成")
                    beats = ["展示包装", "打开包装", "查看材质", "产品与包装同框"]
                    scales = ["wide", "medium", "macro", "close"]
                    plan = {"content_type": "showcase", "relationship": "single",
                            "approval_source": "explicit_fast_request" if fast else "user",
                            "shots": [{"shot_id": "shot-01", "context": "桌面展示", "primary_selling_point": "包装质感",
                                       "purpose": "展示材质", "panel_beats": beats, "shot_scales": scales,
                                       "opening_motif": "包装", "action_motif": "观察材质", "ending_motif": "同框",
                                       "avoid_repeating": [], "intentional_bookend": False}]}
                    self.save("content-plan.json", plan, root)
                    review_id = w.prepare_design_review(root, "shot-01")
                    w.approve_design(root, "shot-01", review_id, "直接生成" if fast else "确认设计")
                    source = self.base / "product.png"
                    Image.new("RGB", (16, 16), "red").save(source)
                    w.add_source(root, source, "image-01")
                    self.save("shared-brief.md", "产品参考为准，木桌自然光", root)
                    panels = [{"position": pos, "start_seconds": i, "end_seconds": i + 1, "time": f"{i}–{i+1}秒",
                               "label": "产品展示", "description": beats[i], "shot_scale": scales[i],
                               "plan_panel_id": f"shot-01:panel-{i+1}"} for i, pos in enumerate(w.POSITIONS)]
                    self.save("shots/shot-01/shot.json", {
                        "references": [{"id": "image-01", "roles": ["product_identity"]}], "review_style": "写实摄影",
                        "review_context": "桌面展示", "review_selling_point": "包装质感", "review_purpose": "展示材质",
                        "sequence_type": "cuts", "camera": "明确切镜", "must_keep": ["产品身份"],
                        "forbidden": ["改变结构"], "panels": panels}, root)
                    prompt = "写实摄影，桌面展示，包装质感，展示材质。\n" + "\n".join(
                        f"{p['time']} {p['label']} {p['description']} {w.SHOT_SCALE_LABELS[p['shot_scale']]}" for p in panels)
                    self.save("shots/shot-01/storyboard-prompt.md", prompt, root)
                    w.check_prompt_plan(root, "shot-01", "当前技术提示词与四格设计相符")
                    if fast:
                        w.set_status(root, "shot-01", "running", True)
                    else:
                        w.set_status(root, "shot-01", "storyboard_prompt_pending", True)
                        rid = w.prepare_prompt_review(root, "shot-01")
                        w.approve(root, "shot-01", "storyboard_prompt", None, rid, "确认当前提示词")
                    w.preflight(root, "shot-01")
                    folder = root / "shots/shot-01"
                    (folder / "generation-prompt-v01.md").write_text(prompt, encoding="utf-8")
                    for name in ("storyboard-v01.png", "storyboard-review-v01.png"):
                        Image.new("RGB", (90, 160), "blue").save(folder / name)
                    self.save("shots/shot-01/shot.json", {"qa": {"result": "pass", "notes": []}}, root)
                    if fast and scope == "storyboard_and_video_prompt":
                        self.save("shots/shot-01/video-prompt.md", "匹配当前图片的视频提示词", root)
                    w.set_status(root, "shot-01", "review_pending" if fast else "storyboard_review_pending", True)
                    approve_artifact(root, "shot-01", "review_package" if fast else "storyboard")
                    if not fast and scope == "storyboard_and_video_prompt":
                        self.save("shots/shot-01/video-prompt.md", "依据已批准图片的文案", root)
                        w.set_status(root, "shot-01", "video_prompt_review_pending", True)
                        approve_artifact(root, "shot-01", "video_prompt")
                    w.validate(root)
                    self.assertEqual(self.data(root)["status"], "complete")
                    self.assertEqual((folder / "storyboard-final.png").read_bytes(), (folder / "storyboard-review-v01.png").read_bytes())


if __name__ == "__main__":
    unittest.main()
