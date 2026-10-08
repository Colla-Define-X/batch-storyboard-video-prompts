import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "chat_membership", Path(__file__).resolve().parents[1] / "scripts/chat_membership.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ChatMembershipTests(unittest.TestCase):
    def state(self):
        return {"thread-project-assignments": {
            "parent": {"projectKind": "local", "projectId": "project-a"}},
            "thread-project-membership-host-ids": {"parent": "local"},
            "projectless-thread-ids": ["child"]}

    def test_explicit_project(self):
        result = MODULE.resolve(self.state(), "parent", "local")
        self.assertEqual(result["project_id"], "project-a")

    def test_explicit_projectless(self):
        self.assertEqual(MODULE.resolve(self.state(), "child", "local")["status"], "projectless")

    def test_absence_is_unknown(self):
        self.assertEqual(MODULE.resolve(self.state(), "absent", "local")["status"], "unknown")

    def test_paths_are_not_membership(self):
        state = {"thread-workspace-root-hints": {"parent": "project-a"}}
        self.assertEqual(MODULE.resolve(state, "parent", "local")["status"], "unknown")

    def test_conflict(self):
        state = self.state()
        state["projectless-thread-ids"].append("parent")
        self.assertEqual(MODULE.resolve(state, "parent", "local")["status"], "unknown")

    def test_remote_not_local(self):
        self.assertEqual(MODULE.resolve(self.state(), "parent", "remote")["status"], "unknown")

    def test_assignment_needs_local_host(self):
        state = self.state()
        state["thread-project-membership-host-ids"] = {}
        self.assertEqual(MODULE.resolve(state, "parent", "local")["status"], "unknown")

    def test_invalid_shapes(self):
        for state in (None, [], {"thread-project-assignments": []},
                      {"projectless-thread-ids": "parent"},
                      {"thread-project-membership-host-ids": []}):
            with self.subTest(state=state):
                self.assertEqual(MODULE.resolve(state, "parent", "local")["status"], "unknown")

    def test_invalid_assignment(self):
        for assignment in (None, "project-a", {}, {"projectKind": "local", "projectId": ""},
                           {"projectKind": "chatgpt", "projectId": "project-a"}):
            state = self.state()
            state["thread-project-assignments"]["parent"] = assignment
            self.assertEqual(MODULE.resolve(state, "parent", "local")["status"], "unknown")

    def test_cli_reads_only_requested_record_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            original = json.dumps(self.state()).encode("utf-8")
            path.write_bytes(original)
            result = subprocess.run([sys.executable, MODULE.__file__, "--thread-id", "parent",
                                     "--host-id", "local", "--state-path", str(path)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["project_id"], "project-a")
            self.assertNotIn('"child"', result.stdout)
            self.assertEqual(path.read_bytes(), original)

    def test_cli_invalid_or_missing_state_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            for exists in (False, True):
                if exists:
                    path.write_text("invalid json", encoding="utf-8")
                result = subprocess.run([sys.executable, MODULE.__file__, "--thread-id", "parent",
                                         "--host-id", "local", "--state-path", str(path)],
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
