from __future__ import annotations

import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest

from test_workflow import (workflow as w, prepare_content_plan, confirm_design,
                           make_image, approve_artifact, record_image)


class CreativeHandoffTests(unittest.TestCase):
    def setUp(self):
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.number = 0

    def project(self, shots=2, scope="storyboard_and_video_prompt"):
        self.number += 1
        root = self.base / f"project-{self.number}"
        w.init_project(root, "creative handoff", shots, delivery=scope)
        prepare_content_plan(root)
        plan = w.read_json(root / "content-plan.json")
        for entry in plan["shots"]:
            entry["panel_beats"] = [
                f"格位：第{i + 1}格；画面与产品状态／动作：产品状态{i + 1}；"
                f"人物动作：手势{i + 1}；视角：斜前方{i + 1}；"
                f"镜头安排：固定机位{i + 1}；本格作用：证明细节{i + 1}"
                for i in range(4)
            ]
        w.write_json(root / "content-plan.json", plan)
        for entry in plan["shots"]:
            confirm_design(root, entry["shot_id"])
        source = root / "input.png"
        make_image(source)
        w.add_source(root, source, "image-01")
        (root / "shared-brief.md").write_text("真实手机摄影，同一桌面场景、自然光与产品不变量。", encoding="utf-8")
        for entry in plan["shots"]:
            data = self.data(root, entry["shot_id"])
            data["references"] = [{"id": "image-01", "roles": ["product_identity"]}]
            w.write_json(w.shot_json_path(root, entry["shot_id"]), data)
        return root

    def data(self, root, sid="shot-01"):
        return w.read_json(w.shot_json_path(root, sid))

    def draft(self, root, sid="shot-01"):
        manifest = w.read_json(root / "project.json")
        entry = next(row for row in w.read_json(root / "content-plan.json")["shots"] if row["shot_id"] == sid)
        data = self.data(root, sid)
        boundaries = manifest["defaults"]["time_boundaries_seconds"]
        data.update(sequence_type="cuts", review_style="真实手机摄影", camera="遵循各格已确认的镜头安排",
                    review_context=entry["context"], review_selling_point=entry["primary_selling_point"],
                    review_purpose=entry["purpose"])
        data["panels"] = [
            {"position": position, "start_seconds": boundaries[i], "end_seconds": boundaries[i + 1],
             "time": f"{boundaries[i]}–{boundaries[i + 1]}秒", "label": f"展示{i + 1}",
             "description": entry["panel_beats"][i], "plan_panel_id": f"{sid}:panel-{i + 1}",
             "shot_scale": entry["shot_scales"][i]}
            for i, position in enumerate(w.POSITIONS)
        ]
        w.write_json(w.shot_json_path(root, sid), data)
        prompt = "\n".join([data[key] for key in ("review_style", "review_context", "review_selling_point", "review_purpose")])
        prompt += "\n" + "\n".join(
            f"{panel['time']} {panel['label']} {panel['description']} {w.SHOT_SCALE_LABELS[panel['shot_scale']]}"
            for panel in data["panels"]
        )
        (root / "shots" / sid / "storyboard-prompt.md").write_text(prompt, encoding="utf-8")
        w.check_prompt_plan(root, sid, "子对话核对六列分项、逐格卖点作用和全批去重复")
        if data["status"] == "todo" and w.review_mode_for(data) == "staged":
            w.set_status(root, sid, "storyboard_prompt_pending", True)

    def launch(self, root, sid="shot-01", mode="all", count=None):
        w.set_concurrency(root, mode, count)
        w.register_task(root, sid, f"child-{sid}", "local")

    def test_default_all_handoff_needs_no_technical_draft(self):
        root = self.project()
        before_design = self.data(root)["design_approvals"]
        self.assertEqual(w.read_json(root / "project.json")["workflow"]["handoff_model"], w.CREATIVE_PLAN_HANDOFF)
        self.assertIn("完整创意已交接", w.task_brief(root, "shot-01"))
        w.set_concurrency(root, "all")
        for sid in ("shot-01", "shot-02"):
            w.register_task(root, sid, f"child-{sid}", "local")
            data = self.data(root, sid)
            self.assertEqual(data["status"], "todo")
            self.assertEqual(data["panels"], [])
            self.assertNotIn("plan_check", data)
            self.assertFalse(data["approvals"])
            self.assertFalse((root / "shots" / sid / "storyboard-prompt.md").exists())
            brief = w.task_brief(root, sid)
            self.assertIn("编写初版提示词", brief)
            self.assertIn("storyboard-prompt-review-template.md", brief)
            self.assertIn("prompt-templates.md", brief)
            self.assertIn("整批分工和其他镜头设计", brief)
            self.assertIn("人物动作", brief)
        manifest = w.read_json(root / "project.json")
        self.assertEqual(manifest["workflow"]["video_prompt_owner"], "shot_task")
        self.assertEqual(self.data(root)["design_approvals"], before_design)
        w.validate(root)

    def test_handoff_also_accepts_prompt_pending_without_prompt(self):
        root = self.project()
        w.set_status(root, "shot-01", "storyboard_prompt_pending", True)
        self.launch(root)
        self.assertIn("编写初版提示词", w.task_brief(root, "shot-01"))
        self.assertFalse((root / "shots/shot-01/storyboard-prompt.md").exists())

    def test_registration_does_not_implicitly_choose_all_or_request_a_pilot_question(self):
        root = self.project()
        before = (root / "project.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "after batch creative approval run set-concurrency all"):
            w.register_task(root, "shot-01", "child", None)
        self.assertEqual((root / "project.json").read_bytes(), before)

    def test_missing_material_or_creative_approval_blocks_initial_gates_atomically(self):
        cases = ("approval", "stale", "references", "roles", "unknown-reference", "duplicate-reference",
                 "source-missing", "source-changed", "brief-missing", "brief-empty", "brief-whitespace")
        for gate in ("launch", "register", "brief"):
            for problem in cases:
                with self.subTest(gate=gate, problem=problem):
                    root = self.project()
                    if gate == "register":
                        w.set_concurrency(root, "all")
                    data = self.data(root)
                    if problem == "approval":
                        data.pop("design_approvals")
                    elif problem == "stale":
                        plan = w.read_json(root / "content-plan.json")
                        plan["shots"][0]["panel_beats"][0] += "；人物改为转动产品"
                        w.write_json(root / "content-plan.json", plan)
                    elif problem == "references":
                        data["references"] = []
                    elif problem == "roles":
                        data["references"][0]["roles"] = []
                    elif problem == "unknown-reference":
                        data["references"][0]["id"] = "unknown"
                    elif problem == "duplicate-reference":
                        data["references"] *= 2
                    elif problem == "source-missing":
                        (root / "sources/image-01.png").unlink()
                    elif problem == "source-changed":
                        (root / "sources/image-01.png").write_bytes(b"changed")
                    elif problem == "brief-missing":
                        (root / "shared-brief.md").unlink()
                    elif problem in {"brief-empty", "brief-whitespace"}:
                        (root / "shared-brief.md").write_text("" if problem == "brief-empty" else " \n", encoding="utf-8")
                    w.write_json(w.shot_json_path(root, "shot-01"), data)
                    before = (root / "project.json").read_bytes()
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        if gate == "launch":
                            w.set_concurrency(root, "all")
                        elif gate == "register":
                            w.register_task(root, "shot-01", "child", None)
                        else:
                            w.task_brief(root, "shot-01")
                    self.assertEqual((root / "project.json").read_bytes(), before)

    def test_initial_pilot_still_requires_the_whole_batch_design_and_materials(self):
        root = self.project()
        data = self.data(root, "shot-02")
        data.pop("design_approvals")
        w.write_json(w.shot_json_path(root, "shot-02"), data)
        with self.assertRaisesRegex(ValueError, "creative approval"):
            w.set_concurrency(root, "pilot", 1)
        confirm_design(root, "shot-02")
        data = self.data(root, "shot-02")
        data["references"] = []
        w.write_json(w.shot_json_path(root, "shot-02"), data)
        with self.assertRaisesRegex(ValueError, "reference IDs and roles"):
            w.set_concurrency(root, "pilot", 1)

    def test_new_marker_cannot_skip_approved_design_by_disabling_content_planning(self):
        root = self.project()
        manifest = w.read_json(root / "project.json")
        manifest["workflow"]["content_plan_required"] = False
        w.write_json(root / "project.json", manifest)
        with self.assertRaisesRegex(ValueError, "version-approved content plan"):
            w.set_concurrency(root, "all")

    def test_initial_handoff_rejects_an_already_generating_unassigned_shot(self):
        root = self.project()
        data = self.data(root)
        data["status"] = "storyboard_generating"
        w.write_json(w.shot_json_path(root, "shot-01"), data)
        with self.assertRaisesRegex(ValueError, "drafting state"):
            w.set_concurrency(root, "all")
        with self.assertRaisesRegex(ValueError, "drafting state"):
            w.task_brief(root, "shot-01")

    def test_every_six_column_component_is_bound_to_creative_approval(self):
        root = self.project()
        original = w.read_json(root / "content-plan.json")
        for component in ("格位", "画面与产品状态／动作", "人物动作", "视角", "镜头安排", "本格作用", "景别"):
            with self.subTest(component=component):
                plan = copy.deepcopy(original)
                if component == "景别":
                    plan["shots"][0]["shot_scales"][0] = "medium"
                else:
                    plan["shots"][0]["panel_beats"][0] = plan["shots"][0]["panel_beats"][0].replace(component + "：", component + "：已修改")
                w.write_json(root / "content-plan.json", plan)
                with self.assertRaisesRegex(ValueError, "stale creative approval"):
                    w.set_concurrency(root, "all")
                with self.assertRaisesRegex(ValueError, "stale creative approval"):
                    w.task_brief(root, "shot-01")

    def test_child_cannot_drop_an_approved_component_from_panel_description(self):
        root = self.project()
        self.launch(root)
        self.draft(root)
        original = self.data(root)
        for component in ("格位", "画面与产品状态／动作", "人物动作", "视角", "镜头安排", "本格作用", "景别"):
            with self.subTest(component=component):
                data = copy.deepcopy(original)
                panel = data["panels"][0]
                if component == "景别":
                    panel["shot_scale"] = "medium"
                else:
                    panel["description"] = "；".join(part for part in panel["description"].split("；") if not part.startswith(component + "："))
                w.write_json(w.shot_json_path(root, "shot-01"), data)
                with self.assertRaisesRegex(ValueError, "differs from approved design"):
                    w.check_prompt_plan(root, "shot-01", "核对本张")

    def test_initial_prompt_review_waits_for_real_registration_and_generation_waits_for_approval(self):
        root = self.project()
        self.draft(root)
        with self.assertRaisesRegex(ValueError, "Register the actual shot task"):
            w.prepare_prompt_review(root, "shot-01")
        self.launch(root)
        with self.assertRaises(ValueError):
            w.preflight(root, "shot-01", "child-shot-01", "local")
        review = w.prepare_prompt_review(root, "shot-01")
        with self.assertRaises(ValueError):
            w.preflight(root, "shot-01", "child-shot-01", "local")
        w.approve(root, "shot-01", "storyboard_prompt", None, review, "确认本张当前提示词")
        before = self.data(root)
        with self.assertRaises(ValueError):
            w.preflight(root, "shot-01", "wrong-child", "local")
        self.assertEqual(self.data(root), before)
        w.preflight(root, "shot-01", "child-shot-01", "local")
        self.assertEqual(self.data(root)["storyboard_version"], 1)

    def test_child_draft_needs_its_own_plan_check_before_review(self):
        root = self.project()
        self.launch(root)
        self.draft(root)
        data = self.data(root)
        data.pop("plan_check")
        w.write_json(w.shot_json_path(root, "shot-01"), data)
        with self.assertRaisesRegex(ValueError, "plan check"):
            w.prepare_prompt_review(root, "shot-01")
        w.check_prompt_plan(root, "shot-01", "逐项比对六列和整批分工")
        w.prepare_prompt_review(root, "shot-01")

    def test_resuming_review_or_approved_prompt_does_not_replace_it(self):
        root = self.project()
        self.launch(root)
        self.draft(root)
        review = w.prepare_prompt_review(root, "shot-01")
        data_before = self.data(root)
        prompt_before = (root / "shots/shot-01/storyboard-prompt.md").read_bytes()
        for _ in range(2):
            self.assertIn("停止并等待", w.task_brief(root, "shot-01"))
            self.assertEqual(self.data(root), data_before)
        w.approve(root, "shot-01", "storyboard_prompt", None, review, "批准当前版本")
        data_before = self.data(root)
        self.assertIn("不要重写提示词", w.task_brief(root, "shot-01"))
        self.assertEqual(self.data(root), data_before)
        self.assertEqual((root / "shots/shot-01/storyboard-prompt.md").read_bytes(), prompt_before)

    def test_child_local_revision_keeps_ownership_and_does_not_touch_other_shots(self):
        root = self.project()
        self.launch(root)
        self.draft(root)
        review = w.prepare_prompt_review(root, "shot-01")
        w.approve(root, "shot-01", "storyboard_prompt", None, review, "确认初版")
        other_before = self.data(root, "shot-02")
        w.revise(root, "shot-01", "storyboard_prompt", "用户要求手停住，不放下笔")
        plan = w.read_json(root / "content-plan.json")
        plan["shots"][0]["panel_beats"][0] += "；人物保持握笔"
        # Another task's incomplete draft must not block this assigned child's work.
        plan["shots"][1]["panel_beats"] = []
        w.write_json(root / "content-plan.json", plan)
        self.assertIn("prepare-design-review", w.task_brief(root, "shot-01"))
        creative_id = w.prepare_design_review(root, "shot-01")
        self.assertIn("当前创意审核记录有效", w.task_brief(root, "shot-01"))
        w.approve_design(root, "shot-01", creative_id, "确认保持握笔的修改")
        self.draft(root)
        review = w.prepare_prompt_review(root, "shot-01")
        w.approve(root, "shot-01", "storyboard_prompt", None, review, "确认本张新版提示词")
        w.preflight(root, "shot-01", "child-shot-01", "local")
        self.assertEqual(self.data(root, "shot-02"), other_before)
        self.assertEqual(w.read_json(root / "project.json")["shots"][0]["task"]["thread_id"], "child-shot-01")

    def test_same_child_continues_to_video_after_image_approval(self):
        root = self.project()
        self.launch(root)
        self.draft(root)
        review = w.prepare_prompt_review(root, "shot-01")
        w.approve(root, "shot-01", "storyboard_prompt", None, review, "确认本张生图提示词")
        record_image(root, thread_id="child-shot-01", host_id="local")
        w.set_status(root, "shot-01", "storyboard_review_pending", True)
        approve_artifact(root, "shot-01", "storyboard")
        task = w.read_json(root / "project.json")["shots"][0]["task"]
        self.assertEqual(task, {"thread_id": "child-shot-01", "host_id": "local", "active": False})
        self.assertIn("在本对话依据已批准并冻结的分镜图编写视频提示词", w.task_brief(root, "shot-01"))
        self.assertIn("不需要重新 register-task 或调用 preflight", w.task_brief(root, "shot-01"))
        (root / "shots/shot-01/video-prompt.md").write_text("依据批准图与运镜计划的视频提示词", encoding="utf-8")
        w.set_status(root, "shot-01", "video_prompt_review_pending", True)
        approve_artifact(root, "shot-01", "video_prompt")
        self.assertEqual(self.data(root)["status"], "complete")
        self.assertIn("不回主对话汇总或审核", w.task_brief(root, "shot-01"))
        w.validate(root)

    def test_image_only_child_completes_without_a_video_prompt(self):
        root = self.project(scope="storyboard_only")
        self.launch(root)
        self.draft(root)
        self.assertNotIn("视频提示词", w.task_brief(root, "shot-01"))
        review = w.prepare_prompt_review(root, "shot-01")
        w.approve(root, "shot-01", "storyboard_prompt", None, review, "确认本张仅图片提示词")
        record_image(root, thread_id="child-shot-01", host_id="local")
        w.set_status(root, "shot-01", "storyboard_review_pending", True)
        approve_artifact(root, "shot-01", "storyboard")
        self.assertEqual(self.data(root)["status"], "complete")
        task = w.read_json(root / "project.json")["shots"][0]["task"]
        self.assertEqual(task, {"thread_id": "child-shot-01", "host_id": "local", "active": False})
        self.assertFalse((root / "shots/shot-01/video-prompt.md").exists())
        self.assertNotIn("视频提示词", w.task_brief(root, "shot-01"))
        w.validate(root)

    def test_explicit_pilot_does_not_roll_forward_without_a_new_user_choice(self):
        root = self.project(shots=3)
        self.launch(root, mode="pilot", count=1)
        w.release_task(root, "shot-01")
        with self.assertRaisesRegex(ValueError, "Pilot scope exhausted"):
            w.register_task(root, "shot-02", "child-shot-02", "local")
        with self.assertRaisesRegex(ValueError, "explicit --reason"):
            w.set_concurrency(root, "all")
        w.set_concurrency(root, "all", reason="用户已看过试做，要求剩余全部继续")
        w.register_task(root, "shot-02", "child-shot-02", "local")
        self.assertFalse((root / "shots/shot-02/storyboard-prompt.md").exists())

    def test_single_and_explicit_fast_still_stay_in_current_conversation(self):
        single = self.project(shots=1)
        self.assertIn("在当前对话处理", w.task_brief(single, "shot-01"))
        with self.assertRaisesRegex(ValueError, "Single storyboard"):
            w.set_concurrency(single, "all")
        self.draft(single)
        w.prepare_prompt_review(single, "shot-01")
        fast = self.project()
        for sid in ("shot-01", "shot-02"):
            w.set_review_mode(fast, sid, "fast", "直接生成，不用逐阶段确认")
            self.assertIn("在当前对话处理", w.task_brief(fast, sid))
        with self.assertRaisesRegex(ValueError, "Fast-mode"):
            w.set_concurrency(fast, "all")
        with self.assertRaisesRegex(ValueError, "Fast-mode"):
            w.register_task(fast, "shot-01", "must-not-create", None)
        self.draft(fast)
        w.set_status(fast, "shot-01", "running", True)
        w.preflight(fast, "shot-01")

    def test_mixed_batch_only_hands_off_staged_shots(self):
        root = self.project()
        w.set_review_mode(root, "shot-02", "fast", "第二张直接生成")
        data = self.data(root, "shot-02")
        data["references"] = []  # This current-chat shot will prepare its own inputs.
        w.write_json(w.shot_json_path(root, "shot-02"), data)
        self.launch(root)
        self.assertIn("编写初版提示词", w.task_brief(root, "shot-01"))
        self.assertIn("在当前对话处理", w.task_brief(root, "shot-02"))
        with self.assertRaisesRegex(ValueError, "Fast-mode"):
            w.register_task(root, "shot-02", "must-not-create", None)


if __name__ == "__main__":
    unittest.main()
