#!/usr/bin/env python3
"""Read explicit local Codex desktop membership; never infer it from paths.

This is a compatibility adapter for desktop state, not a public Codex API.
Validate returned project IDs with list_projects before creating a chat.
"""

import argparse
import json
import os
from pathlib import Path


def resolve(state, thread_id, host_id):
    unknown = {"status": "unknown", "thread_id": thread_id}
    if host_id != "local" or not isinstance(state, dict):
        return {**unknown, "reason": "Only local desktop state is supported"}
    assignments = state.get("thread-project-assignments", {})
    projectless = state.get("projectless-thread-ids", [])
    hosts = state.get("thread-project-membership-host-ids", {})
    if (not isinstance(assignments, dict) or not isinstance(projectless, list)
            or not all(isinstance(x, str) for x in projectless)
            or not isinstance(hosts, dict)):
        return {**unknown, "reason": "Unsupported desktop state format"}
    assigned = thread_id in assignments
    unassigned = thread_id in projectless
    if assigned and unassigned:
        return {**unknown, "reason": "Conflicting explicit membership records"}
    if hosts.get(thread_id) not in (None, "local"):
        return {**unknown, "reason": "Membership host differs"}
    if assigned:
        value = assignments[thread_id]
        if (not isinstance(value, dict) or value.get("projectKind") != "local"
                or not isinstance(value.get("projectId"), str)
                or not value["projectId"].strip()
                or hosts.get(thread_id) != "local"):
            return {**unknown, "reason": "Unsupported or unverified assignment"}
        return {"status": "project", "thread_id": thread_id,
                "project_id": value["projectId"], "source": "desktop_explicit_assignment"}
    if unassigned:
        return {"status": "projectless", "thread_id": thread_id,
                "source": "desktop_explicit_projectless"}
    return {**unknown, "reason": "No explicit membership record"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--host-id", required=True)
    parser.add_argument("--state-path", type=Path,
                        help="Optional exact desktop state file; read-only")
    args = parser.parse_args()
    root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    path = args.state_path or root / ".codex-global-state.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8-sig"))
        result = resolve(state, args.thread_id, args.host_id)
    except (OSError, ValueError):
        result = {"status": "unknown", "thread_id": args.thread_id,
                  "reason": "Desktop state unavailable or invalid"}
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["status"] != "unknown" else 2


if __name__ == "__main__":
    raise SystemExit(main())
