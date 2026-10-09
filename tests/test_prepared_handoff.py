from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from test_workflow import (workflow as w, prepare, prepare_all, prepare_content_plan,
                           mark_legacy_handoff, approve_prompt, approve_artifact, record_image)


class PreparedHandoffTests(unittest.TestCase):
    def setUp(self):
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.draft_number = 0

    def project(self, name="new", shots=2, scope="storyboard_and_video_prompt"):
        root = self.base / name
        w.init_project(root, name, shots, delivery=scope)
        # Existing prepared-prompt projects must retain their old first-launch gate.
        manifest = w.read_json(root / "project.json")
        manifest["workflow"]["handoff_model"] = w.PREPARED_PROMPT_HANDOFF
        w.write_json(root / "project.json", manifest)
        return root

    def data(self, root, sid="shot-01"):
        return w.read_json(w.shot_json_path(root, sid))

    def save(self, root, relative, value):
        self.draft_number += 1
        draft = self.base / f"owner-{self.draft_number}.txt"
        draft.write_text(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value,
                         encoding="utf-8")
        return w.save_content(root, relative, draft, w.content_revision(root, relative))

    def test_prepared_launch_needs_every_staged_prompt_prepared_atomically(self):
        root = self.project()
        self.assertEqual(w.read_json(root / "project.json")["workflow"]["handoff_model"],
                         "prepared_prompt_to_shot")
        prepare_content_plan(root)
        before = (root / "project.json").read_bytes()
        with self.assertRaises(ValueError):
            w.set_concurrency(root, "pilot", 1)
        self.assertEqual((root / "project.json").read_bytes(), before)
        prepare(root, "shot-01")
        w.set_status(root, "shot-01", "storyboard_prompt_pending", True)
        before = (root / "project.json").read_bytes()
        with self.assertRaises(ValueError):
            w.set_concurrency(root, "pilot", 1)
        self.assertEqual((root / "project.json").read_bytes(), before)
        with self.assertRaises(ValueError):
            w.task_brief(root, "shot-02")
        prepare_all(root)
        w.set_concurrency(root, "pilot", 1)
        self.assertEqual(w.read_json(root / "project.json")["workflow"]["video_prompt_owner"], "shot_task")
        self.assertFalse(self.data(root)["approvals"])
        self.assertFalse(self.data(root, "shot-02")["approvals"])

    def test_stale_check_blocks_initial_launch_and_first_registration(self):
        root = self.project("stale")
        prepare_all(root)
        prompt = root / "shots/shot-02/storyboard-prompt.md"
        self.save(root, "shots/shot-02/storyboard-prompt.md", prompt.read_text(encoding="utf-8") + "\n摄影补充")
        before = (root / "project.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "plan check"):
            w.set_concurrency(root, "all")
        self.assertEqual((root / "project.json").read_bytes(), before)
        w.check_prompt_plan(root, "shot-02", "核对第二张的摄影补充")
        w.set_concurrency(root, "all")
        self.save(root, "shots/shot-01/storyboard-prompt.md",
                  (root / "shots/shot-01/storyboard-prompt.md").read_text(encoding="utf-8") + "\n局部补充")
        before = (root / "project.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "plan check"):
            w.register_task(root, "shot-01", "child-01", None)
        self.assertEqual((root / "project.json").read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "plan check"):
            w.task_brief(root, "shot-01")
        w.check_prompt_plan(root, "shot-01", "核对第一张的局部补充")
        w.register_task(root, "shot-01", "child-01", None)

    def test_first_prompt_review_waits_for_task_registration(self):
        root = self.project("first-review")
        prepare_all(root)
        w.set_concurrency(root, "pilot", 1)
        self.assertIn("等待总控登记真实任务 ID", w.task_brief(root, "shot-01"))
        with self.assertRaises(ValueError):
            w.prepare_prompt_review(root, "shot-01")
        self.assertNotIn("prompt_review", self.data(root))
        w.register_task(root, "shot-01", "child-01", None)
        with self.assertRaises(ValueError):
            w.preflight(root, "shot-01", "child-01")
        review_id = w.prepare_prompt_review(root, "shot-01")
        self.assertIn("停止并等待", w.task_brief(root, "shot-01"))
        self.assertIn("停止并等待", w.task_brief(root, "shot-01"))
        self.assertEqual(self.data(root)["prompt_review"]["id"], review_id)
        w.approve(root, "shot-01", "storyboard_prompt", None, review_id, "确认当前子任务展示的提示词")
        w.preflight(root, "shot-01", "child-01")
        self.assertEqual(self.data(root)["storyboard_version"], 1)

    def test_child_can_revise_prompt_and_recheck_it_locally(self):
        root = self.project("local-revision")
        prepare_all(root)
        w.set_concurrency(root, "all")
        w.register_task(root, "shot-01", "child-01", None)
        original_id = w.prepare_prompt_review(root, "shot-01")
        w.approve(root, "shot-01", "storyboard_prompt", None, original_id, "确认初稿")
        w.revise(root, "shot-01", "storyboard_prompt", "用户要求补摄影细节")
        prompt = root / "shots/shot-01/storyboard-prompt.md"
        self.save(root, "shots/shot-01/storyboard-prompt.md", prompt.read_text(encoding="utf-8") + "\n柔和逆光")
        brief = w.task_brief(root, "shot-01")
        self.assertIn("check-prompt-plan", brief)
        self.assertIn("不需要主对话复核", brief)
        w.check_prompt_plan(root, "shot-01", "子对话核对摄影细节和跨镜头避重")
        self.assertIn("当前完整提示词和四格数据已准备好", w.task_brief(root, "shot-01"))
        new_id = w.prepare_prompt_review(root, "shot-01")
        self.assertNotEqual(new_id, original_id)
        with self.assertRaises(ValueError):
            w.approve(root, "shot-01", "storyboard_prompt", None, original_id, "初稿旧回复")
        w.approve(root, "shot-01", "storyboard_prompt", None, new_id, "确认修订后版本")
        w.preflight(root, "shot-01", "child-01")

    def test_assigned_child_handles_creative_revision_without_new_task(self):
        root = self.project("creative-revision")
        prepare_all(root)
        w.set_concurrency(root, "all")
        w.register_task(root, "shot-01", "child-01", None)
        w.revise(root, "shot-01", "storyboard_prompt", "用户要求改本镜头设计")
        plan = w.read_json(root / "content-plan.json")
        other_entry = dict(plan["shots"][1])
        plan["shots"][0]["context"] = "新展示场景"
        self.save(root, "content-plan.json", plan)
        before = self.data(root)
        brief = w.task_brief(root, "shot-01")
        self.assertIn("prepare-design-review", brief)
        review_id = w.prepare_design_review(root, "shot-01")
        self.assertIn("当前创意审核记录有效", w.task_brief(root, "shot-01"))
        self.assertEqual(self.data(root)["design_review"]["id"], review_id)
        self.assertEqual(self.data(root)["revisions"], before["revisions"])
        w.approve_design(root, "shot-01", review_id, "确认本子任务的新设计")
        self.assertEqual(w.read_json(root / "content-plan.json")["shots"][1], other_entry)
        self.save(root, "shots/shot-01/shot.json", {"review_context": "新展示场景"})
        prompt = root / "shots/shot-01/storyboard-prompt.md"
        self.save(root, "shots/shot-01/storyboard-prompt.md",
                  prompt.read_text(encoding="utf-8").replace("场景1", "新展示场景"))
        w.check_prompt_plan(root, "shot-01", "本子对话核对新场景与其他镜头避重")
        prompt_id = w.prepare_prompt_review(root, "shot-01")
        w.approve(root, "shot-01", "storyboard_prompt", None, prompt_id, "确认本张修改后的提示词")
        task = w.read_json(root / "project.json")["shots"][0]["task"]
        self.assertEqual(task, {"thread_id": "child-01", "host_id": None, "active": True})
        w.preflight(root, "shot-01", "child-01")
        self.assertEqual(self.data(root)["storyboard_version"], 1)

    def test_small_edit_before_first_review_needs_local_recheck(self):
        root = self.project("first-edit")
        prepare_all(root)
        w.set_concurrency(root, "all")
        w.register_task(root, "shot-01", "child-01", None)
        prompt = root / "shots/shot-01/storyboard-prompt.md"
        self.save(root, "shots/shot-01/storyboard-prompt.md",
                  prompt.read_text(encoding="utf-8") + "\n按用户要求增加柔和轮廓光")
        self.assertFalse(self.data(root).get("revisions"))
        self.assertIn("check-prompt-plan", w.task_brief(root, "shot-01"))
        with self.assertRaisesRegex(ValueError, "plan check"):
            w.prepare_prompt_review(root, "shot-01")
        w.check_prompt_plan(root, "shot-01", "核对用户要求的摄影补充，不改变核心设计")
        self.assertIn("当前完整提示词和四格数据已准备好", w.task_brief(root, "shot-01"))
        review_id = w.prepare_prompt_review(root, "shot-01")
        self.assertEqual(self.data(root)["prompt_review"]["id"], review_id)

    def test_multishot_image_only_completes_in_child_without_video(self):
        root = self.project("image-only", scope="storyboard_only")
        prepare_all(root)
        w.set_concurrency(root, "pilot", 1)
        w.register_task(root, "shot-01", "child-01", None)
        self.assertNotIn("视频提示词", w.task_brief(root, "shot-01"))
        approve_prompt(root)
        record_image(root, thread_id="child-01")
        w.set_status(root, "shot-01", "storyboard_review_pending", True)
        approve_artifact(root, "shot-01", "storyboard")
        self.assertEqual(self.data(root)["status"], "complete")
        task = w.read_json(root / "project.json")["shots"][0]["task"]
        self.assertFalse(task["active"])
        self.assertEqual(task["thread_id"], "child-01")
        self.assertNotIn("视频提示词", w.task_brief(root, "shot-01"))
        self.assertFalse((root / "shots/shot-01/video-prompt.md").exists())
        w.validate(root)

    def test_same_child_handles_video_then_completes_without_new_slot(self):
        root = self.project("video-owner")
        prepare_all(root)
        w.set_concurrency(root, "pilot", 1)
        w.register_task(root, "shot-01", "child-01", None)
        approve_prompt(root)
        record_image(root, thread_id="child-01")
        w.set_status(root, "shot-01", "storyboard_review_pending", True)
        approve_artifact(root, "shot-01", "storyboard")
        task = w.read_json(root / "project.json")["shots"][0]["task"]
        self.assertEqual(task["thread_id"], "child-01")
        self.assertFalse(task["active"])
        brief = w.task_brief(root, "shot-01")
        self.assertIn("在本对话依据已批准并冻结的分镜图编写视频提示词", brief)
        self.assertIn("不需要重新 register-task 或调用 preflight", brief)
        self.save(root, "shots/shot-01/video-prompt.md", "依据本张已批准图片的视频提示词")
        w.set_status(root, "shot-01", "video_prompt_review_pending", True)
        self.assertIn("在本对话等待用户对当前版本的确认", w.task_brief(root, "shot-01"))
        approve_artifact(root, "shot-01", "video_prompt")
        self.assertEqual(self.data(root)["status"], "complete")
        brief = w.task_brief(root, "shot-01")
        self.assertIn("已完成", brief)
        self.assertIn("不回主对话汇总或审核", brief)
        self.assertEqual(w.read_json(root / "project.json")["shots"][0]["task"]["thread_id"], "child-01")
        w.validate(root)

    def test_legacy_without_marker_retains_old_unlaunched_behavior(self):
        root = self.project("legacy")
        mark_legacy_handoff(root)
        prepare_content_plan(root)
        self.assertIn("按已确认的四格画面与景别写技术提示词", w.task_brief(root, "shot-01"))
        w.set_concurrency(root, "all")
        w.register_task(root, "shot-01", "legacy-child", None)
        self.assertEqual(w.read_json(root / "project.json")["workflow"]["video_prompt_owner"], "coordinator")

    def test_old_pilot_image_revision_cannot_bypass_current_pilot_choice(self):
        root = self.project("pilot-revisit")
        prepare_all(root)
        w.set_concurrency(root, "pilot", 1)
        w.register_task(root, "shot-01", "first-child", None)
        approve_prompt(root)
        record_image(root, thread_id="first-child")
        w.set_status(root, "shot-01", "storyboard_review_pending", True)
        approve_artifact(root, "shot-01", "storyboard")
        self.assertFalse(w.read_json(root / "project.json")["shots"][0]["task"]["active"])
        w.set_concurrency(root, "pilot", 1, reason="用户明确先试第二张")
        w.register_task(root, "shot-02", "second-child", None)
        w.revise(root, "shot-01", "storyboard", "用户要求旧图重做")
        before = self.data(root)
        with self.assertRaisesRegex(ValueError, "outside the authorized pilot"):
            w.preflight(root, "shot-01", "first-child")
        self.assertEqual(self.data(root), before)
        self.assertEqual(self.data(root)["storyboard_version"], 1)

    def test_single_and_fast_stay_local_and_image_only_brief_stays_in_scope(self):
        single = self.project("single", shots=1, scope="storyboard_only")
        prepare_content_plan(single)
        self.assertIn("在当前对话处理", w.task_brief(single, "shot-01"))
        self.assertNotIn("视频提示词及交付", w.task_brief(single, "shot-01"))
        mixed = self.project("mixed")
        w.set_review_mode(mixed, "shot-02", "fast", "第二张直接生成")
        prepare_all(mixed)
        w.set_concurrency(mixed, "all")
        self.assertEqual(w.read_json(mixed / "project.json")["workflow"]["video_prompt_owner"], "shot_task")
        self.assertIn("在当前对话处理", w.task_brief(mixed, "shot-02"))
        with self.assertRaisesRegex(ValueError, "Fast-mode"):
            w.register_task(mixed, "shot-02", "fast-child", None)
        w.register_task(mixed, "shot-01", "staged-child", None)
        self.assertIn("本子对话独立负责", w.task_brief(mixed, "shot-01"))


if __name__ == "__main__":
    unittest.main()
