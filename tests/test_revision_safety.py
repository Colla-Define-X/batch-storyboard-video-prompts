from __future__ import annotations

import contextlib
import copy
import io
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_workflow import workflow as w, prepare, prepare_all, prepare_content_plan, confirm_design, approve_prompt, record_image, approve_artifact, mark_legacy_handoff
import project_io


def content_writer(root, draft, revision, event, results):
    event.wait(10)
    try:
        w.save_content(Path(root), "shots/shot-01/shot.json", Path(draft), revision)
        results.put("saved")
    except ValueError as exc:
        results.put("conflict" if "version conflict" in str(exc) else str(exc))


class RevisionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        w.init_project(self.root, "safety", 3)
        prepare_content_plan(self.root)

    def draft(self, name, value):
        path = Path(self.temp.name) / name
        path.write_text(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value, encoding="utf-8")
        return path

    def test_failed_command_does_not_restore_unrelated_shot_or_shared_content(self):
        mark_legacy_handoff(self.root)
        prepare(self.root)
        w.set_status(self.root, "shot-01", "storyboard_prompt_pending", True)
        path1 = w.shot_json_path(self.root, "shot-01")
        path2 = w.shot_json_path(self.root, "shot-02")
        before = path1.read_bytes()
        writer = w.write_json
        def fail_after_write(path, data):
            writer(path, data)
            if path == path1:
                # Simulate a separate owner writing outside this command's context.
                other = w.read_json(path2)
                other["camera"] = "other owner's new content"
                path2.write_text(json.dumps(other), encoding="utf-8")
                (self.root / "shared-brief.md").write_text("new shared content", encoding="utf-8")
                raise OSError("shot-01 failed")
        with patch.object(w, "write_json", side_effect=fail_after_write), self.assertRaises(OSError):
            w.prepare_prompt_review(self.root, "shot-01")
        self.assertEqual(path1.read_bytes(), before)
        self.assertEqual(w.read_json(path2)["camera"], "other owner's new content")
        self.assertEqual((self.root / "shared-brief.md").read_text(encoding="utf-8"), "new shared content")

    def test_conflicting_out_of_band_write_is_preserved_and_recovery_stops(self):
        prepare(self.root)
        path = w.shot_json_path(self.root, "shot-01")
        writer = w.write_json
        def fail_after_external_edit(target, data):
            writer(target, data)
            if target == path:
                external = w.read_json(path)
                external["camera"] = "new external content"
                path.write_text(json.dumps(external), encoding="utf-8")
                raise OSError("command failed")
        with patch.object(w, "write_json", side_effect=fail_after_external_edit), self.assertRaisesRegex(RuntimeError, "Recovery conflict"):
            w.prepare_design_review(self.root, "shot-01")
        self.assertEqual(w.read_json(path)["camera"], "new external content")
        self.assertTrue((self.root / ".workflow-transaction.json").exists())
        with self.assertRaisesRegex(RuntimeError, "Recovery conflict"):
            w.validate(self.root)

    def test_recovery_is_repeatable_after_interruption(self):
        first, second = self.root / "first.txt", self.root / "second.txt"
        first.write_bytes(b"old-first")
        second.write_bytes(b"old-second")
        @project_io.transaction
        def fail(root):
            project_io.atomic_bytes(first, b"new-first")
            project_io.atomic_bytes(second, b"new-second")
            raise OSError("failure")
        recovery = project_io.recover
        with patch.object(project_io, "recover", side_effect=lambda root: None if not (root / ".workflow-transaction.json").exists() else (_ for _ in ()).throw(OSError("recovery interrupted"))):
            with self.assertRaises(OSError):
                fail(self.root)
        first.write_bytes(b"old-first")  # Simulate one already-restored file.
        recovery(self.root)
        self.assertEqual(first.read_bytes(), b"old-first")
        self.assertEqual(second.read_bytes(), b"old-second")
        self.assertFalse((self.root / ".workflow-transaction.json").exists())

    def test_legacy_journal_is_preserved_for_explicit_recovery(self):
        journal = self.root / ".workflow-transaction.json"
        journal.write_text(json.dumps({"shared-brief.md": None}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Legacy transaction journal"):
            w.validate(self.root)
        self.assertTrue(journal.exists())
        self.assertTrue((self.root / "shared-brief.md").exists())

    def test_content_save_rejects_stale_revision_and_control_fields(self):
        target = "shots/shot-01/shot.json"
        revision = w.content_revision(self.root, target)
        draft = self.draft("camera.json", {"camera": "new camera"})
        w.save_content(self.root, target, draft, revision)
        with self.assertRaisesRegex(ValueError, "version conflict"):
            w.save_content(self.root, target, self.draft("stale.json", {"camera": "stale"}), revision)
        for field in ("status", "approvals", "design_approvals", "generation_claimed"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "content fields only"):
                w.save_content(self.root, target, self.draft("bad.json", {field: "invalid"}), w.content_revision(self.root, target))

    def test_parallel_content_saves_do_not_lose_updates_silently(self):
        revision = w.content_revision(self.root, "shots/shot-01/shot.json")
        drafts = [self.draft(f"worker-{i}.json", {"camera": f"camera-{i}"}) for i in range(2)]
        ctx = multiprocessing.get_context("spawn")
        event, results = ctx.Event(), ctx.Queue()
        workers = [ctx.Process(target=content_writer, args=(str(self.root), str(draft), revision, event, results)) for draft in drafts]
        for worker in workers:
            worker.start()
        event.set()
        for worker in workers:
            worker.join(20)
            if worker.is_alive():
                worker.terminate()
                worker.join()
                self.fail("Content writer hung")
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(sorted(results.get(timeout=5) for _ in workers), ["conflict", "saved"])
        results.close()

    def test_content_save_requires_revision_before_editing_approved_prompt(self):
        mark_legacy_handoff(self.root)
        prepare(self.root)
        w.set_status(self.root, "shot-01", "storyboard_prompt_pending", True)
        approve_prompt(self.root)
        target = "shots/shot-01/storyboard-prompt.md"
        with self.assertRaisesRegex(ValueError, "Use revise"):
            w.save_content(self.root, target, self.draft("prompt.md", "changed"), w.content_revision(self.root, target))

    def test_content_save_allows_generation_qa_but_not_panel_semantic_changes(self):
        mark_legacy_handoff(self.root)
        prepare(self.root)
        w.set_status(self.root, "shot-01", "storyboard_prompt_pending", True)
        approve_prompt(self.root)
        target = "shots/shot-01/shot.json"
        data = w.read_json(w.shot_json_path(self.root, "shot-01"))
        data["panels"][0]["image"] = "panels/panel-v01-01.png"
        w.save_content(self.root, target, self.draft("paths.json", {"panels": data["panels"], "qa": {"result": "not_run"}}), w.content_revision(self.root, target))
        data["panels"][0]["description"] = "changed design"
        with self.assertRaisesRegex(ValueError, "only panel image paths"):
            w.save_content(self.root, target, self.draft("bad-panel.json", {"panels": data["panels"]}), w.content_revision(self.root, target))

    def test_grouped_design_swap_renews_only_selected_assignments(self):
        before_third = w.read_json(w.shot_json_path(self.root, "shot-03"))
        w.revise_designs(self.root, ["shot-01", "shot-02"], "用户互换前两张设计")
        plan = w.read_json(self.root / "content-plan.json")
        first, second = copy.deepcopy(plan["shots"][:2])
        plan["shots"][:2] = [dict(second, shot_id="shot-01"), dict(first, shot_id="shot-02")]
        w.write_json(self.root / "content-plan.json", plan)
        for sid in ("shot-01", "shot-02"):
            confirm_design(self.root, sid)
            records = w.read_json(w.shot_json_path(self.root, sid))["design_approvals"]
            self.assertTrue(records[0]["invalidated_at"])
            self.assertNotIn("invalidated_at", records[-1])
        w.content_plan(self.root, w.read_json(self.root / "project.json"))
        self.assertEqual(w.read_json(w.shot_json_path(self.root, "shot-03")), before_third)

    def test_group_revision_preserves_duplicate_check_against_unaffected_shots(self):
        w.revise_designs(self.root, ["shot-01", "shot-02"], "用户改前两张")
        plan = w.read_json(self.root / "content-plan.json")
        for key in ("opening_motif", "action_motif", "ending_motif"):
            plan["shots"][0][key] = plan["shots"][2][key]
        w.write_json(self.root / "content-plan.json", plan)
        with self.assertRaisesRegex(ValueError, "repeats a complete action arc"):
            w.prepare_design_review(self.root, "shot-01")

    def test_group_revision_rollback_and_old_review_ids(self):
        ids = ["shot-01", "shot-02"]
        paths = [w.shot_json_path(self.root, sid) for sid in ids]
        before = [path.read_bytes() for path in paths]
        old_id = w.read_json(paths[0])["design_review"]["id"]
        writer = w.write_json
        def fail_second(path, data):
            if path == paths[1]:
                raise OSError("failed second write")
            writer(path, data)
        with patch.object(w, "write_json", side_effect=fail_second), self.assertRaises(OSError):
            w.revise_designs(self.root, ids, "用户一起改")
        self.assertEqual([path.read_bytes() for path in paths], before)
        w.revise_designs(self.root, ids, "用户一起改")
        with self.assertRaisesRegex(ValueError, "stale creative review"):
            w.approve_design(self.root, "shot-01", old_id, "旧回复")
        with self.assertRaisesRegex(ValueError, "stale creative approval"):
            w.content_plan(self.root, w.read_json(self.root / "project.json"), "shot-01")

    def test_group_revision_rejects_active_tasks_and_bad_selection(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "all")
        w.register_task(self.root, "shot-01", "task-1", None)
        with self.assertRaisesRegex(ValueError, "release affected"):
            w.revise_designs(self.root, ["shot-01", "shot-02"], "互换")
        for ids, reason in (([], "改"), (["shot-02", "shot-02"], "改"), (["shot-02"], " ")):
            with self.assertRaises(ValueError):
                w.revise_designs(self.root, ids, reason)

    def test_prompt_review_brief_waits_then_reports_stale_without_rewriting(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "all")
        w.register_task(self.root, "shot-01", "review-task", None)
        self.assertIn("当前完整提示词和四格数据已准备好", w.task_brief(self.root, "shot-01"))
        w.prepare_prompt_review(self.root, "shot-01")
        brief = w.task_brief(self.root, "shot-01")
        self.assertIn("停止并等待", brief)
        self.assertNotIn("按已确认的四格画面与景别写技术提示词", brief)
        path = self.root / "shots/shot-01/storyboard-prompt.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nnew detail", encoding="utf-8")
        brief = w.task_brief(self.root, "shot-01")
        self.assertIn("审核已过期", brief)
        self.assertNotIn("按已确认的四格画面与景别写技术提示词", brief)
        w.revise(self.root, "shot-01", "storyboard_prompt", "用户要求修改")
        self.assertIn("执行 check-prompt-plan", w.task_brief(self.root, "shot-01"))

    def test_pilot_scope_survives_release_and_retries_but_not_new_shots(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-02", "pilot-task", None)
        w.release_task(self.root, "shot-02")
        with self.assertRaisesRegex(ValueError, "Pilot scope exhausted"):
            w.register_task(self.root, "shot-01", "next-task", None)
        w.register_task(self.root, "shot-02", "same-shot-again", None)
        w.release_task(self.root, "shot-02")
        with self.assertRaisesRegex(ValueError, "explicit --reason"):
            w.set_concurrency(self.root, "pilot", 1)
        w.set_concurrency(self.root, "all", reason="用户看过效果后要求全部继续")
        w.register_task(self.root, "shot-01", "next-task", None)
        w.validate(self.root)

    def test_pilot_active_task_cannot_be_replaced_without_release(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "task-a", "host-a")
        manifest = self.root / "project.json"
        before = manifest.read_bytes()
        for thread_id, host_id in (("task-b", "host-a"), ("task-a", "host-b")):
            with self.subTest(thread_id=thread_id, host_id=host_id):
                with self.assertRaisesRegex(ValueError, "stop and release"):
                    w.register_task(self.root, "shot-01", thread_id, host_id)
                self.assertEqual(manifest.read_bytes(), before)
        w.validate(self.root)

    def test_duplicate_task_registration_is_idempotent(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "task-a", "host-a")
        manifest = self.root / "project.json"
        before = manifest.read_bytes()
        w.register_task(self.root, "shot-01", "task-a", "host-a")
        self.assertEqual(manifest.read_bytes(), before)
        self.assertEqual(w.read_json(manifest)["workflow"]["pilot_shot_ids"], ["shot-01"])

    def test_release_allows_replacement_for_same_pilot_shot(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "task-a", "host-a")
        w.release_task(self.root, "shot-01")
        w.register_task(self.root, "shot-01", "task-b", "host-b")
        project = w.read_json(self.root / "project.json")
        self.assertEqual(project["shots"][0]["task"], {"thread_id": "task-b", "host_id": "host-b", "active": True})
        self.assertEqual(project["workflow"]["pilot_shot_ids"], ["shot-01"])
        w.validate(self.root)

    def test_multi_staged_preflight_rejects_missing_or_wrong_task_identity_before_claim(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "task-a", "host-a")
        approve_prompt(self.root)
        path = w.shot_json_path(self.root, "shot-01")
        before = path.read_bytes()
        for thread_id, host_id, message in (
            (None, None, "requires the calling task's --thread-id"),
            ("wrong-task", "host-a", "does not match"),
            ("task-a", None, "does not match"),
            ("task-a", "host-b", "does not match"),
        ):
            with self.subTest(thread_id=thread_id, host_id=host_id):
                with self.assertRaisesRegex(ValueError, message):
                    w.preflight(self.root, "shot-01", thread_id, host_id)
                self.assertEqual(path.read_bytes(), before)
        w.preflight(self.root, "shot-01", "task-a", "host-a")
        data = w.read_json(path)
        self.assertEqual(data["storyboard_version"], 1)
        self.assertTrue(data["generation_claimed"])
        with self.assertRaisesRegex(ValueError, "already claimed"):
            w.preflight(self.root, "shot-01", "task-a", "host-a")

    def test_preflight_handoff_rejects_old_task_and_accepts_new_owner(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "task-a", "host-a")
        approve_prompt(self.root)
        w.release_task(self.root, "shot-01")
        w.register_task(self.root, "shot-01", "task-b", "host-b")
        path = w.shot_json_path(self.root, "shot-01")
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "does not match"):
            w.preflight(self.root, "shot-01", "task-a", "host-a")
        self.assertEqual(path.read_bytes(), before)
        w.preflight(self.root, "shot-01", "task-b", "host-b")
        self.assertTrue(w.read_json(path)["generation_claimed"])
        w.release_task(self.root, "shot-01")
        w.register_task(self.root, "shot-01", "task-c", "host-c")
        with self.assertRaisesRegex(ValueError, "already claimed"):
            w.preflight(self.root, "shot-01", "task-c", "host-c")

    def test_cli_preflight_accepts_registered_identity_without_host(self):
        prepare_all(self.root)
        brief = w.task_brief(self.root, "shot-01")
        self.assertIn("总控在创建并登记任务后单独告知", brief)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "task-a", None)
        self.assertNotIn("task-a", w.task_brief(self.root, "shot-01"))
        approve_prompt(self.root)
        script = Path(w.__file__).resolve()
        command = [sys.executable, "-X", "utf8", str(script), "preflight", str(self.root), "shot-01"]
        missing = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("--thread-id", missing.stderr)
        self.assertIsNone(w.read_json(w.shot_json_path(self.root, "shot-01"))["storyboard_version"])
        accepted = subprocess.run(command + ["--thread-id", "task-a"], capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertTrue(w.read_json(w.shot_json_path(self.root, "shot-01"))["generation_claimed"])

    def test_cli_preflight_checks_registered_host(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "task-a", "host-a")
        approve_prompt(self.root)
        script = Path(w.__file__).resolve()
        command = [sys.executable, "-X", "utf8", str(script), "preflight", str(self.root), "shot-01",
                   "--thread-id", "task-a"]
        wrong_host = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(wrong_host.returncode, 0)
        self.assertIn("does not match", wrong_host.stderr)
        self.assertIsNone(w.read_json(w.shot_json_path(self.root, "shot-01"))["storyboard_version"])
        accepted = subprocess.run(command + ["--host-id", "host-a"], capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertTrue(w.read_json(w.shot_json_path(self.root, "shot-01"))["generation_claimed"])

    def test_completed_pilot_does_not_authorize_next_shot(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "pilot-task", None)
        approve_prompt(self.root)
        record_image(self.root, thread_id="pilot-task")
        w.set_status(self.root, "shot-01", "storyboard_review_pending", True)
        approve_artifact(self.root, "shot-01", "storyboard", "仅确认这张图")
        with self.assertRaisesRegex(ValueError, "Pilot scope exhausted"):
            w.register_task(self.root, "shot-02", "unauthorized-next", None)

    def test_validation_rejects_task_outside_pilot_scope(self):
        prepare_all(self.root)
        w.set_concurrency(self.root, "pilot", 1)
        w.register_task(self.root, "shot-01", "first", None)
        w.release_task(self.root, "shot-01")
        project = w.read_json(self.root / "project.json")
        project["shots"][1]["task"] = {"thread_id": "forged", "active": True}
        w.write_json(self.root / "project.json", project)
        with self.assertRaisesRegex(ValueError, "outside the authorized pilot"):
            w.validate(self.root)

    def test_new_commands_work_through_cli(self):
        command = [sys.executable, "-X", "utf8", str(Path(w.__file__))]
        revision = w.content_revision(self.root, "shots/shot-01/shot.json")
        draft = self.draft("cli.json", {"camera": "CLI update"})
        for args in (["save-content", str(self.root), "shots/shot-01/shot.json", "--from-file", str(draft), "--expected-hash", revision],
                     ["revise-designs", str(self.root), "shot-01", "shot-02", "--reason", "用户互换"]):
            result = subprocess.run(command + args, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_project_content_patch_cannot_change_task_authorization(self):
        draft = self.draft("project-patch.json", {"workflow": {"parallel_launch_mode": "all"}})
        with self.assertRaisesRegex(ValueError, "Project content patch"):
            w.save_content(self.root, "project.json", draft, w.content_revision(self.root, "project.json"))
        draft = self.draft("project-patch.json", {"delivery_scope": "storyboard_only"})
        w.save_content(self.root, "project.json", draft, w.content_revision(self.root, "project.json"))
        self.assertEqual(w.read_json(self.root / "project.json")["delivery_scope"], "storyboard_only")

    def test_new_source_is_rolled_back_if_its_manifest_write_fails(self):
        from PIL import Image
        source = Path(self.temp.name) / "source.png"
        Image.new("RGB", (16, 16), "red").save(source)
        with patch.object(w, "write_json", side_effect=OSError("manifest failure")), self.assertRaises(OSError):
            w.add_source(self.root, source, "image-new")
        self.assertFalse((self.root / "sources/image-new.png").exists())
        self.assertTrue(source.exists())

    @unittest.skipUnless(os.name == "nt", "Windows temporary sharing violations")
    def test_atomic_replace_retries_transient_windows_sharing_error(self):
        target = Path(self.temp.name) / "atomic.txt"
        original = Path.replace
        attempts = []
        error = PermissionError("temporarily held")
        error.winerror = 32
        def replace(path, destination):
            attempts.append(1)
            if len(attempts) == 1:
                raise error
            return original(path, destination)
        with patch.object(Path, "replace", replace), patch.object(project_io.time, "sleep"):
            project_io.atomic_bytes(target, b"saved")
        self.assertEqual(target.read_bytes(), b"saved")
        self.assertEqual(len(attempts), 2)


if __name__ == "__main__":
    unittest.main()
