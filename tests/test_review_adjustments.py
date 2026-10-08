from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from test_workflow import workflow as w


class ReviewAdjustmentTests(unittest.TestCase):
    def setUp(self):
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.draft_number = 0

    def save(self, root, relative, value):
        revision = w.content_revision(root, relative)
        self.draft_number += 1
        draft = self.base / f"owner-draft-{self.draft_number}.txt"
        draft.write_text(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value,
                         encoding="utf-8")
        return w.save_content(root, relative, draft, revision)

    def data(self, root):
        return w.read_json(w.shot_json_path(root, "shot-01"))

    def prepared(self, name, fast=False, scope="storyboard_and_video_prompt"):
        # Editable inputs use the public save protocol; only image-tool outputs
        # and owner-local drafts are written directly by these fixtures.
        root = self.base / name
        w.init_project(root, "review adjustments", delivery=scope)
        if fast:
            w.set_review_mode(root, "shot-01", "fast", "用户明确要求直接生成")
        beats = ["展示包装", "打开包装", "查看材质", "产品与包装同框"]
        scales = ["wide", "medium", "macro", "close"]
        self.save(root, "content-plan.json", {
            "content_type": "showcase", "relationship": "single",
            "approval_source": "explicit_fast_request" if fast else "user",
            "shots": [{"shot_id": "shot-01", "context": "桌面展示", "primary_selling_point": "包装质感",
                       "purpose": "展示材质", "panel_beats": beats, "shot_scales": scales,
                       "opening_motif": "包装", "action_motif": "观察材质", "ending_motif": "同框",
                       "avoid_repeating": [], "intentional_bookend": False}],
        })
        design_id = w.prepare_design_review(root, "shot-01")
        w.approve_design(root, "shot-01", design_id, "直接生成" if fast else "确认设计")
        source = self.base / f"{name}-product.png"
        Image.new("RGB", (16, 16), "red").save(source)
        w.add_source(root, source, "image-01")
        self.save(root, "shared-brief.md", "产品参考为准，木桌自然光")
        panels = [{"position": position, "start_seconds": i, "end_seconds": i + 1,
                   "time": f"{i}–{i+1}秒", "label": "产品展示", "description": beats[i],
                   "shot_scale": scales[i], "plan_panel_id": f"shot-01:panel-{i+1}"}
                  for i, position in enumerate(w.POSITIONS)]
        self.save(root, "shots/shot-01/shot.json", {
            "references": [{"id": "image-01", "roles": ["product_identity"]}],
            "review_style": "写实摄影", "review_context": "桌面展示",
            "review_selling_point": "包装质感", "review_purpose": "展示材质",
            "sequence_type": "cuts", "camera": "明确切镜", "must_keep": ["产品身份"],
            "forbidden": ["改变结构"], "panels": panels,
        })
        prompt = "写实摄影，桌面展示，包装质感，展示材质。\n" + "\n".join(
            f"{panel['time']} {panel['label']} {panel['description']} {w.SHOT_SCALE_LABELS[panel['shot_scale']]}"
            for panel in panels)
        self.save(root, "shots/shot-01/storyboard-prompt.md", prompt)
        w.check_prompt_plan(root, "shot-01", "已核对当前设计与技术提示词")
        if not fast:
            w.set_status(root, "shot-01", "storyboard_prompt_pending", True)
        return root

    def authorize(self, root, fast=False):
        if fast:
            w.set_status(root, "shot-01", "running", True)
        else:
            review_id = w.prepare_prompt_review(root, "shot-01")
            w.approve(root, "shot-01", "storyboard_prompt", None, review_id, "确认本版提示词")

    def image_result(self, root, image=True, qa=True, size=(90, 160)):
        w.preflight(root, "shot-01")
        path = w.shot_json_path(root, "shot-01").parent / "storyboard-review-v01.png"
        if image:
            Image.new("RGB", size, "blue").save(path)
        if qa:
            self.save(root, "shots/shot-01/shot.json", {"qa": {"result": "pass", "notes": []}})
        return path

    def image_review(self, name, fast=False, scope="storyboard_and_video_prompt"):
        root = self.prepared(name, fast, scope)
        self.authorize(root, fast)
        self.image_result(root)
        if fast and scope == "storyboard_and_video_prompt":
            self.save(root, "shots/shot-01/video-prompt.md", "匹配当前图片的视频提示词")
        w.set_status(root, "shot-01", "review_pending" if fast else "storyboard_review_pending", True)
        return root

    def make_inputs_stale(self, root, kind):
        if kind == "brief":
            self.save(root, "shared-brief.md", "用户更新了共享摄影要求")
        elif kind == "plan":
            plan = w.read_json(root / "content-plan.json")
            plan["content_type"] = "mixed"
            self.save(root, "content-plan.json", plan)
        else:
            # Simulate a dependency becoming unavailable outside the workflow.
            (root / "sources/image-01.png").unlink()

    def test_finished_result_can_revise_despite_stale_shared_inputs(self):
        for fast in (False, True):
            for kind in ("brief", "plan", "source"):
                for grouped in (False, True):
                    with self.subTest(fast=fast, kind=kind, grouped=grouped):
                        root = self.prepared(f"stale-{fast}-{kind}-{grouped}", fast)
                        self.authorize(root, fast)
                        image = self.image_result(root)
                        before = image.read_bytes()
                        old = self.data(root)
                        self.make_inputs_stale(root, kind)
                        with self.assertRaises((ValueError, FileNotFoundError)):
                            w.review_binding(root, w.read_json(root / "project.json"), self.data(root))
                        if grouped:
                            w.revise_designs(root, ["shot-01"], "用户要求按新输入修订设计")
                        else:
                            w.revise(root, "shot-01", "storyboard_prompt", "用户要求按新输入修订提示词")
                        revised = self.data(root)
                        self.assertEqual(revised["status"], "todo" if fast else "storyboard_prompt_pending")
                        self.assertFalse(revised["generation_claimed"])
                        self.assertIsNone(revised["generation_binding"])
                        self.assertEqual(revised["storyboard_version"], old["storyboard_version"])
                        self.assertEqual(image.read_bytes(), before)
                        self.assertNotIn("prompt_review", revised)
                        if grouped:
                            self.assertTrue(revised["design_approvals"][-1]["invalidated_at"])
                        if not fast:
                            self.assertTrue(revised["approvals"][-1]["invalidated_at"])
                        with self.assertRaises(ValueError):
                            w.preflight(root, "shot-01")
                        with self.assertRaises(ValueError):
                            w.approve(root, "shot-01", "review_package" if fast else "storyboard",
                                      None, "old-result", "确认旧图")

    def test_incomplete_result_still_blocks_revision_when_inputs_are_stale(self):
        for fast in (False, True):
            for missing in ("image", "qa", "ratio"):
                with self.subTest(fast=fast, missing=missing):
                    root = self.prepared(f"incomplete-{fast}-{missing}", fast)
                    self.authorize(root, fast)
                    self.image_result(root, image=missing != "image", qa=missing != "qa",
                                      size=(100, 100) if missing == "ratio" else (90, 160))
                    self.make_inputs_stale(root, "brief")
                    before = w.shot_json_path(root, "shot-01").read_bytes()
                    for grouped in (False, True):
                        with self.subTest(grouped=grouped), self.assertRaisesRegex(ValueError, "Wait for the claimed"):
                            if grouped:
                                w.revise_designs(root, ["shot-01"], "用户修改设计")
                            else:
                                w.revise(root, "shot-01", "storyboard_prompt", "用户修改提示词")
                        self.assertEqual(w.shot_json_path(root, "shot-01").read_bytes(), before)

    def test_design_resubmission_uses_new_id_for_identical_content(self):
        root = self.prepared("design-id")
        old = self.data(root)["design_review"]
        w.revise_designs(root, ["shot-01"], "用户撤回并重新提交相同设计")
        new_id = w.prepare_design_review(root, "shot-01")
        self.assertNotEqual(new_id, old["id"])
        self.assertEqual(self.data(root)["design_review"]["binding"], old["binding"])
        with self.assertRaisesRegex(ValueError, "stale creative review"):
            w.approve_design(root, "shot-01", old["id"], "原审核轮次回复")
        newest_id = w.prepare_design_review(root, "shot-01")
        self.assertNotEqual(newest_id, new_id)
        with self.assertRaisesRegex(ValueError, "stale creative review"):
            w.approve_design(root, "shot-01", new_id, "上一轮回复")
        w.approve_design(root, "shot-01", newest_id, "确认重新展示的当前设计")

    def test_prompt_resubmission_uses_new_id_for_identical_content(self):
        root = self.prepared("prompt-id")
        old_id = w.prepare_prompt_review(root, "shot-01")
        old = self.data(root)["prompt_review"]
        w.revise(root, "shot-01", "storyboard_prompt", "用户撤回并重新提交相同提示词")
        new_id = w.prepare_prompt_review(root, "shot-01")
        self.assertNotEqual(new_id, old_id)
        self.assertEqual(self.data(root)["prompt_review"]["binding"], old["binding"])
        self.assertEqual(self.data(root)["prompt_review"]["summary_hash"], old["summary_hash"])
        with self.assertRaisesRegex(ValueError, "stale prompt review"):
            w.approve(root, "shot-01", "storyboard_prompt", None, old_id, "原审核轮次回复")
        newest_id = w.prepare_prompt_review(root, "shot-01")
        self.assertNotEqual(newest_id, new_id)
        with self.assertRaisesRegex(ValueError, "stale prompt review"):
            w.approve(root, "shot-01", "storyboard_prompt", None, new_id, "上一轮回复")
        w.approve(root, "shot-01", "storyboard_prompt", None, newest_id, "确认重新展示的当前提示词")
        w.preflight(root, "shot-01")

    def test_existing_approvals_remain_valid_without_new_submission(self):
        root = self.prepared("existing-approval")
        self.authorize(root)
        before = self.data(root)
        for _ in range(2):
            w.validate(root)
            w.check_generation(root, w.read_json(root / "project.json"), self.data(root))
        self.assertEqual(self.data(root), before)
        w.preflight(root, "shot-01")
        self.assertEqual(self.data(root)["approvals"], before["approvals"])
        self.assertEqual(self.data(root)["design_approvals"], before["design_approvals"])

    def test_pending_qa_notes_require_new_review_without_new_image(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.image_review(f"qa-notes-{fast}", fast)
                before = self.data(root)
                image = w.shot_json_path(root, "shot-01").parent / "storyboard-review-v01.png"
                image_bytes = image.read_bytes()
                qa = {"result": "pass_with_notes", "notes": ["边缘留白略窄，主体与标签均完整"]}
                self.save(root, "shots/shot-01/shot.json", {"qa": qa})
                revised = self.data(root)
                self.assertEqual(revised["qa"], qa)
                self.assertNotIn("artifact_review", revised)
                for key in ("status", "storyboard_version", "generation_binding", "generation_claimed", "approvals"):
                    self.assertEqual(revised[key], before[key])
                self.assertEqual(image.read_bytes(), image_bytes)
                stage = "review_package" if fast else "storyboard"
                old_id = before["artifact_review"]["id"]
                with self.assertRaisesRegex(ValueError, "stale artifact review"):
                    w.approve(root, "shot-01", stage, None, old_id, "旧 QA 回复")
                new_id = w.prepare_artifact_review(root, "shot-01")
                self.assertNotEqual(new_id, old_id)
                with self.assertRaisesRegex(ValueError, "stale artifact review"):
                    w.approve(root, "shot-01", stage, None, old_id, "旧 QA 回复")
                w.approve(root, "shot-01", stage, None, new_id, "确认图片与更新后的 QA 说明")
                w.validate(root)
                self.assertEqual(image.read_bytes(), image_bytes)
                self.assertEqual(self.data(root)["storyboard_version"], 1)

    def test_identical_pending_qa_preserves_current_review(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.image_review(f"qa-identical-{fast}", fast)
                before = self.data(root)
                self.save(root, "shots/shot-01/shot.json", {"qa": before["qa"]})
                self.assertEqual(self.data(root), before)
                w.approve(root, "shot-01", "review_package" if fast else "storyboard", None,
                          before["artifact_review"]["id"], "确认本版图片")

    def test_pending_qa_permission_does_not_open_other_shot_fields(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.image_review(f"qa-fields-{fast}", fast)
                path = w.shot_json_path(root, "shot-01")
                before = path.read_bytes()
                panels = self.data(root)["panels"]
                panels[0]["image"] = "panels/other.png"
                for changes in ({"camera": "新运镜"}, {"panels": panels}, {"references": []},
                                {"qa": {"result": "pass", "notes": ["备注"]}, "camera": "新运镜"}):
                    with self.subTest(fields=list(changes)), self.assertRaisesRegex(ValueError, "revise"):
                        self.save(root, "shots/shot-01/shot.json", changes)
                    self.assertEqual(path.read_bytes(), before)
                with self.assertRaisesRegex(ValueError, "revise"):
                    self.save(root, "shots/shot-01/storyboard-prompt.md", "修改提示词")

    def test_complete_does_not_allow_qa_edit(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.image_review(f"qa-complete-{fast}", fast, "storyboard_only")
                w.approve(root, "shot-01", "review_package" if fast else "storyboard", None,
                          self.data(root)["artifact_review"]["id"], "确认完成")
                before = self.data(root)
                with self.assertRaisesRegex(ValueError, "revise"):
                    self.save(root, "shots/shot-01/shot.json", {"qa": {"result": "pass", "notes": ["新备注"]}})
                self.assertEqual(self.data(root), before)

    def test_pending_qa_write_failure_restores_qa_and_review_together(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.image_review(f"qa-rollback-{fast}", fast)
                path = w.shot_json_path(root, "shot-01")
                before = path.read_bytes()
                project_before = (root / "project.json").read_bytes()
                writer = w.write_json

                def fail_after_write(target, data):
                    writer(target, data)
                    if target == path:
                        raise OSError("simulated QA write failure")

                with patch.object(w, "write_json", side_effect=fail_after_write), self.assertRaises(OSError):
                    self.save(root, "shots/shot-01/shot.json", {"qa": {"result": "pass_with_notes", "notes": ["新备注"]}})
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual((root / "project.json").read_bytes(), project_before)
                self.assertFalse((root / ".workflow-transaction.json").exists())
                w.approve(root, "shot-01", "review_package" if fast else "storyboard", None,
                          self.data(root)["artifact_review"]["id"], "确认原 QA 与图片")

    def test_pending_review_rejects_invalid_qa_without_losing_review(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.image_review(f"qa-invalid-{fast}", fast)
                before = w.shot_json_path(root, "shot-01").read_bytes()
                invalid = [None, "pass", {}, {"result": "not_run"}, {"result": True},
                           {"result": "pass", "notes": "remark"},
                           {"result": "failed", "notes": [1]}]
                for qa in invalid:
                    with self.subTest(qa=qa), self.assertRaisesRegex(ValueError, "Pending QA"):
                        self.save(root, "shots/shot-01/shot.json", {"qa": qa})
                    self.assertEqual(w.shot_json_path(root, "shot-01").read_bytes(), before)
                self.save(root, "shots/shot-01/shot.json", {"qa": {"result": "pass_with_notes"}})
                self.assertEqual(self.data(root)["qa"], {"result": "pass_with_notes"})
                self.assertNotIn("artifact_review", self.data(root))

    def test_severe_pending_qa_stops_until_explicit_retry_and_new_preflight(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.image_review(f"qa-severe-{fast}", fast)
                before = self.data(root)
                image = w.shot_json_path(root, "shot-01").parent / "storyboard-review-v01.png"
                image_bytes = image.read_bytes()
                self.save(root, "shots/shot-01/shot.json", {"qa": {"result": "failed", "notes": []}})
                failed = self.data(root)
                target = "running" if fast else "storyboard_generating"
                self.assertEqual(failed["status"], "failed" if fast else "generation_failed")
                self.assertEqual(failed["failed_from"], target)
                self.assertEqual(w.read_json(root / "project.json")["shots"][0]["status"], failed["status"])
                for key in ("storyboard_version", "generation_binding", "generation_claimed"):
                    self.assertEqual(failed[key], before[key])
                self.assertEqual(image.read_bytes(), image_bytes)
                self.assertNotIn("artifact_review", failed)
                self.assertEqual(failed.get("retries", []), before.get("retries", []))
                with self.assertRaises(ValueError):
                    w.approve(root, "shot-01", "review_package" if fast else "storyboard", None,
                              before["artifact_review"]["id"], "原图片回复")
                with self.assertRaises(ValueError):
                    w.preflight(root, "shot-01")
                with self.assertRaises(ValueError):
                    w.retry_shot(root, "shot-01", target, None)
                self.assertEqual(self.data(root), failed)
                w.validate(root)
                w.retry_shot(root, "shot-01", target, "用户看过严重缺陷后要求重试")
                self.assertEqual(self.data(root)["storyboard_version"], 1)
                self.assertFalse(self.data(root)["generation_claimed"])
                w.preflight(root, "shot-01")
                self.assertEqual(self.data(root)["storyboard_version"], 2)
                self.assertTrue(self.data(root)["generation_claimed"])
                self.assertEqual(self.data(root)["qa"]["result"], "not_run")
                self.assertEqual(image.read_bytes(), image_bytes)

    def test_severe_qa_summary_write_failure_restores_both_manifests(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.image_review(f"qa-severe-rollback-{fast}", fast)
                path = w.shot_json_path(root, "shot-01")
                before = path.read_bytes()
                project_before = (root / "project.json").read_bytes()
                writer = w.write_json

                def fail_after_project_write(target, data):
                    writer(target, data)
                    if target == root / "project.json":
                        raise OSError("simulated failure after summary write")

                with patch.object(w, "write_json", side_effect=fail_after_project_write), self.assertRaises(OSError):
                    self.save(root, "shots/shot-01/shot.json", {"qa": {"result": "failed", "notes": ["主体结构错误"]}})
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual((root / "project.json").read_bytes(), project_before)
                self.assertFalse((root / ".workflow-transaction.json").exists())
                w.approve(root, "shot-01", "review_package" if fast else "storyboard", None,
                          self.data(root)["artifact_review"]["id"], "确认原本有效的审核")

    def test_severe_qa_during_fast_video_revision_cannot_approve_old_image(self):
        root = self.image_review("qa-fast-video-revision", fast=True)
        w.approve(root, "shot-01", "review_package", None,
                  self.data(root)["artifact_review"]["id"], "确认原完整包")
        image = w.shot_json_path(root, "shot-01").parent / "storyboard-final.png"
        image_bytes = image.read_bytes()
        w.revise(root, "shot-01", "video_prompt", "用户只修改文案")
        self.save(root, "shots/shot-01/video-prompt.md", "修改后的文案")
        review_id = w.prepare_artifact_review(root, "shot-01")
        self.save(root, "shots/shot-01/shot.json", {"qa": {"result": "failed", "notes": ["复核发现产品结构错误"]}})
        failed = self.data(root)
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["failed_from"], "running")
        self.assertTrue(failed["approvals"][-1]["invalidated_at"])
        self.assertEqual(failed["storyboard_version"], 1)
        self.assertTrue(failed["generation_claimed"])
        self.assertEqual(image.read_bytes(), image_bytes)
        with self.assertRaises(ValueError):
            w.approve(root, "shot-01", "review_package", None, review_id, "确认修改文案")
        with self.assertRaises(ValueError):
            w.prepare_artifact_review(root, "shot-01")
        with self.assertRaises(ValueError):
            w.revise(root, "shot-01", "video_prompt", "继续只改文案")
        with self.assertRaisesRegex(ValueError, "revise"):
            self.save(root, "shots/shot-01/video-prompt.md", "再次修改文案")
        self.assertEqual(self.data(root), failed)
        w.validate(root)

    def test_withdrawn_unapproved_prompt_allows_delivery_scope_change(self):
        root = self.prepared("scope-withdraw")
        old_id = w.prepare_prompt_review(root, "shot-01")
        with self.assertRaisesRegex(ValueError, "scope is locked"):
            self.save(root, "project.json", {"delivery_scope": "storyboard_only"})
        w.revise(root, "shot-01", "storyboard_prompt", "用户撤回未批准提示词，改为只交图片")
        self.save(root, "project.json", {"delivery_scope": "storyboard_only"})
        self.assertEqual(w.read_json(root / "project.json")["delivery_scope"], "storyboard_only")
        self.assertFalse(self.data(root).get("approvals"))
        self.assertFalse(self.data(root).get("storyboard_version"))
        with self.assertRaisesRegex(ValueError, "stale prompt review"):
            w.approve(root, "shot-01", "storyboard_prompt", None, old_id, "旧范围回复")
        w.check_prompt_plan(root, "shot-01", "核对仅图片交付的新版本")
        self.authorize(root)
        w.preflight(root, "shot-01")
        self.assertEqual(self.data(root)["storyboard_version"], 1)

    def test_withdrawal_does_not_unlock_scope_with_approval_or_generation_history(self):
        for fast in (False, True):
            with self.subTest(fast=fast):
                root = self.prepared(f"scope-history-{fast}", fast)
                self.authorize(root, fast)
                if fast:
                    self.image_result(root)
                w.revise(root, "shot-01", "storyboard_prompt", "用户返回提示词修改")
                before = self.data(root)
                project_before = (root / "project.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "scope is locked"):
                    self.save(root, "project.json", {"delivery_scope": "storyboard_only"})
                self.assertEqual(self.data(root), before)
                self.assertEqual((root / "project.json").read_bytes(), project_before)


if __name__ == "__main__":
    unittest.main()
