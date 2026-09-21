#!/usr/bin/env python3
"""Initialize and coordinate staged storyboard projects with fast-mode compatibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


FAST_STATUSES = ("todo", "running", "review_pending", "complete", "failed")
LEGACY_STATUSES = (
    "shot_card_pending", "storyboard_prompt_pending", "storyboard_generating", "storyboard_pending",
    "storyboard_review_pending", "video_prompt_pending", "video_prompt_review_pending", "generation_failed",
)
STATUSES = FAST_STATUSES + LEGACY_STATUSES


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_shot(project: dict, shot_id: str) -> dict:
    matches = [shot for shot in project["shots"] if shot["id"] == shot_id]
    if not matches:
        raise KeyError(f"Unknown shot: {shot_id}")
    return matches[0]


def shot_json_path(root: Path, shot_id: str) -> Path:
    return root / "shots" / shot_id / "shot.json"


def legacy_state_path(root: Path, shot_id: str) -> Path:
    return root / "shots" / shot_id / "state.json"


def init_project(root: Path, name: str, shots: int) -> None:
    if shots < 1:
        raise ValueError("--shots must be positive")
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Refusing to initialize non-empty directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "sources").mkdir()
    rows = []
    for index in range(1, shots + 1):
        shot_id = f"shot-{index:02d}"
        (root / "shots" / shot_id / "panels").mkdir(parents=True)
        title = f"镜头{index}"
        rows.append({
            "id": shot_id, "title": title, "status": "todo",
            "task": {"thread_id": None, "host_id": None},
        })
        write_json(shot_json_path(root, shot_id), {
            "shot_id": shot_id, "title": title, "status": "todo",
            "references": [], "panels": [], "camera": "",
            "must_keep": [], "forbidden": [],
            "qa": {"result": "not_run", "notes": []},
            "storyboard_version": None,
        })
    write_json(root / "project.json", {
        "schema_version": 3,
        "name": name,
        "defaults": {
            "ratio": "9:16", "layout": "2x2", "duration_seconds": 5,
            "duration_policy": {"minimum_seconds": 4, "typical_range_seconds": [5, 10]},
            "reading_order": ["top_left", "top_right", "bottom_left", "bottom_right"],
            "time_ranges": ["0–1秒", "1–2.5秒", "2.5–4秒", "4–5秒"],
            "video_resolution": "1080p", "audio": "无对白、无旁白、仅极轻环境声",
        },
        "workflow": {
            "mode": "staged_customer_review", "cross_shot_parallel": True,
            "approval": "storyboard_prompt_then_storyboard_then_video_prompt",
            "one_visible_task_per_shot": True,
        },
        "shots": rows,
    })


def add_source(root: Path, source: Path, asset_id: str) -> None:
    path = root / "project.json"
    project = read_json(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    target = root / "sources" / f"{asset_id}{source.suffix.lower()}"
    if target.exists():
        raise FileExistsError(f"Stable source already exists: {target}")
    shutil.copy2(source, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    project.setdefault("assets", []).append({
        "id": asset_id, "source_name": source.name,
        "stable_path": str(target.relative_to(root)), "sha256": digest,
    })
    write_json(path, project)


def write_shot_status(root: Path, project: dict, shot_id: str, status: str) -> None:
    schema = project.get("schema_version", 1)
    if schema >= 3:
        path = shot_json_path(root, shot_id)
        shot_data = read_json(path)
        shot_data["status"] = status
        write_json(path, shot_data)
    else:
        write_json(legacy_state_path(root, shot_id), {"shot_id": shot_id, "status": status})


def set_status(root: Path, shot_id: str, status: str, coordinator: bool) -> None:
    path = root / "project.json"
    project = read_json(path)
    shot = find_shot(project, shot_id)
    write_shot_status(root, project, shot_id, status)
    if coordinator:
        shot["status"] = status
        write_json(path, project)


def sync_statuses(root: Path) -> None:
    path = root / "project.json"
    project = read_json(path)
    schema = project.get("schema_version", 1)
    for shot in project["shots"]:
        state_path = shot_json_path(root, shot["id"]) if schema >= 3 else legacy_state_path(root, shot["id"])
        if state_path.exists():
            data = read_json(state_path)
            if data.get("shot_id") != shot["id"] or data.get("status") not in STATUSES:
                raise ValueError(f"Invalid shot state: {shot['id']}")
            shot["status"] = data["status"]
    write_json(path, project)


def register_task(root: Path, shot_id: str, thread_id: str, host_id: str | None) -> None:
    path = root / "project.json"
    project = read_json(path)
    shot = find_shot(project, shot_id)
    shot["task"] = {"thread_id": thread_id, "host_id": host_id}
    write_json(path, project)


def validate(root: Path) -> None:
    project = read_json(root / "project.json")
    schema = project.get("schema_version")
    if schema not in (1, 2, 3):
        raise ValueError("Unsupported schema_version")
    ids = [shot["id"] for shot in project.get("shots", [])]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate shot IDs")
    for shot in project.get("shots", []):
        if shot.get("status") not in STATUSES:
            raise ValueError(f"Invalid status for {shot.get('id')}")
        shot_dir = root / "shots" / shot["id"]
        if not shot_dir.is_dir():
            raise FileNotFoundError(f"Missing shot directory: {shot['id']}")
        if schema >= 3:
            data = read_json(shot_json_path(root, shot["id"]))
            if data.get("shot_id") != shot["id"] or data.get("status") not in STATUSES:
                raise ValueError(f"Invalid shot.json: {shot['id']}")
        else:
            state_path = legacy_state_path(root, shot["id"])
            if state_path.exists():
                state = read_json(state_path)
                if state.get("shot_id") != shot["id"] or state.get("status") not in STATUSES:
                    raise ValueError(f"Invalid state file: {shot['id']}")
    for asset in project.get("assets", []):
        source = root / asset["stable_path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError(f"Source hash mismatch: {asset['id']}")
    print(f"OK: schema v{schema}, {len(ids)} shots, {len(project.get('assets', []))} stable sources")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("root", type=Path)
    init.add_argument("--name", required=True)
    init.add_argument("--shots", type=int, required=True)
    source = sub.add_parser("add-source")
    source.add_argument("root", type=Path)
    source.add_argument("source", type=Path)
    source.add_argument("--id", required=True)
    for command in ("status", "shot-status"):
        status = sub.add_parser(command)
        status.add_argument("root", type=Path)
        status.add_argument("shot_id")
        status.add_argument("status", choices=STATUSES)
    sync = sub.add_parser("sync")
    sync.add_argument("root", type=Path)
    task = sub.add_parser("register-task")
    task.add_argument("root", type=Path)
    task.add_argument("shot_id")
    task.add_argument("thread_id")
    task.add_argument("--host-id")
    check = sub.add_parser("validate")
    check.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.command == "init":
        init_project(args.root, args.name, args.shots)
    elif args.command == "add-source":
        add_source(args.root, args.source, args.id)
    elif args.command == "status":
        set_status(args.root, args.shot_id, args.status, coordinator=True)
    elif args.command == "shot-status":
        set_status(args.root, args.shot_id, args.status, coordinator=False)
    elif args.command == "sync":
        sync_statuses(args.root)
    elif args.command == "register-task":
        register_task(args.root, args.shot_id, args.thread_id, args.host_id)
    elif args.command == "validate":
        validate(args.root)


if __name__ == "__main__":
    main()
