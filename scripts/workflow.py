#!/usr/bin/env python3
"""Initialize and coordinate reviewed storyboard projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


POSITIONS = ("top_left", "top_right", "bottom_left", "bottom_right")
ASSET_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

FAST_STATUSES = ("todo", "running", "review_pending", "complete", "failed")
STAGED_STATUSES = (
    "todo", "storyboard_prompt_pending", "storyboard_generating",
    "storyboard_review_pending", "video_prompt_pending",
    "video_prompt_review_pending", "complete", "generation_failed",
)
LEGACY_STATUSES = ("shot_card_pending", "storyboard_pending")
STATUSES = tuple(dict.fromkeys(FAST_STATUSES + STAGED_STATUSES + LEGACY_STATUSES))

STAGED_TRANSITIONS = {
    "todo": {"storyboard_prompt_pending"},
    "storyboard_prompt_pending": set(),
    "storyboard_generating": {"storyboard_review_pending", "generation_failed"},
    "storyboard_review_pending": {"storyboard_generating"},
    "video_prompt_pending": {"video_prompt_review_pending", "generation_failed"},
    "video_prompt_review_pending": {"video_prompt_pending"},
    "generation_failed": set(),
    "complete": set(),
}
FAST_TRANSITIONS = {
    "todo": {"running"},
    "running": {"review_pending", "failed"},
    "review_pending": {"running"},
    "failed": set(),
    "complete": set(),
}
APPROVAL_TRANSITIONS = {
    "staged": {
        "storyboard_prompt": ("storyboard_prompt_pending", "storyboard_generating"),
        "storyboard": ("storyboard_review_pending", "video_prompt_pending"),
        "video_prompt": ("video_prompt_review_pending", "complete"),
    },
    "fast": {
        "review_package": ("review_pending", "complete"),
    },
}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


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


def normalize_number(value: float) -> int | float:
    rounded = round(float(value), 3)
    return int(rounded) if rounded.is_integer() else rounded


def derive_time_boundaries(duration: float) -> list[int | float]:
    if isinstance(duration, bool):
        raise ValueError("Shot duration must be at least 4 seconds")
    try:
        numeric_duration = float(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError("Shot duration must be a finite number of at least 4 seconds") from exc
    if not math.isfinite(numeric_duration) or numeric_duration < 4:
        raise ValueError("Shot duration must be at least 4 seconds")
    return [normalize_number(numeric_duration * ratio) for ratio in (0, 0.2, 0.5, 0.8, 1)]


def format_time_ranges(boundaries: list[int | float]) -> list[str]:
    return [f"{start}–{end}秒" for start, end in zip(boundaries, boundaries[1:])]


def write_shared_brief(root: Path, name: str) -> None:
    path = root / "shared-brief.md"
    if path.exists():
        return
    path.write_text(
        f"# {name} — 共享视觉规范\n\n"
        "总控对话维护本文件；镜头任务只读取，不复制整段公共背景。\n\n"
        "## 视觉连续性\n\n- 待总控确认并填写。\n\n"
        "## 产品与包装不变量\n\n- 待总控确认并填写。\n\n"
        "## 灯光、场景与构图\n\n- 待总控确认并填写。\n\n"
        "## 声音与交付\n\n- 无对白、无旁白、仅极轻环境声。\n",
        encoding="utf-8",
    )


def init_project(root: Path, name: str, shots: int, duration: float = 5) -> None:
    if shots < 1:
        raise ValueError("--shots must be positive")
    boundaries = derive_time_boundaries(duration)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise FileExistsError(f"Refusing to initialize non-empty path: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "sources").mkdir()
    write_shared_brief(root, name)
    rows = []
    for index in range(1, shots + 1):
        shot_id = f"shot-{index:02d}"
        (root / "shots" / shot_id / "panels").mkdir(parents=True)
        title = f"镜头{index}"
        rows.append({
            "id": shot_id, "title": title, "status": "todo",
            "review_mode": "staged",
            "task": {"thread_id": None, "host_id": None, "active": False},
        })
        write_json(shot_json_path(root, shot_id), {
            "shot_id": shot_id, "title": title, "status": "todo",
            "review_mode": "staged", "review_mode_source": "default",
            "review_mode_reason": None, "approvals": [], "retries": [],
            "references": [], "panels": [], "camera": "",
            "must_keep": [], "forbidden": [],
            "qa": {"result": "not_run", "notes": []},
            "storyboard_version": None,
        })
    write_json(root / "project.json", {
        "schema_version": 4,
        "name": name,
        "defaults": {
            "ratio": "9:16", "layout": "2x2", "duration_seconds": normalize_number(duration),
            "duration_policy": {"minimum_seconds": 4, "typical_range_seconds": [5, 10]},
            "reading_order": list(POSITIONS),
            "time_boundaries_seconds": boundaries,
            "time_ranges": format_time_ranges(boundaries),
            "video_resolution": "1080p", "audio": "无对白、无旁白、仅极轻环境声",
        },
        "workflow": {
            "default_review_mode": "staged", "cross_shot_parallel": True,
            "approval": "storyboard_prompt_then_storyboard_then_video_prompt",
            "execution_model": "coordinator_with_shot_slots",
            "parallel_launch_mode": None,
            "max_parallel_shot_tasks": None,
            "shared_brief_path": "shared-brief.md",
            "retry_policy": "explicit_user_request_only",
            "video_prompt_owner": "coordinator",
            "one_visible_task_per_shot": True,
        },
        "shots": rows,
    })


def validate_asset_id(asset_id: str) -> None:
    if len(asset_id) > 64 or not ASSET_ID_PATTERN.fullmatch(asset_id):
        raise ValueError("Asset ID must be 1-64 lowercase letters, digits, or single hyphens")


def verify_image(path: Path) -> None:
    try:
        from PIL import Image
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError(f"Invalid image file: {path}") from exc


def add_source(root: Path, source: Path, asset_id: str) -> None:
    path = root / "project.json"
    project = read_json(path)
    validate_asset_id(asset_id)
    if not source.is_file():
        raise FileNotFoundError(source)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError(f"Unsupported image type: {suffix or '<none>'}")
    verify_image(source)
    assets = project.setdefault("assets", [])
    if any(asset.get("id") == asset_id for asset in assets):
        raise ValueError(f"Duplicate asset ID: {asset_id}")

    sources_dir = (root / "sources").resolve()
    target = (sources_dir / f"{asset_id}{suffix}").resolve()
    if not target.is_relative_to(sources_dir):
        raise ValueError(f"Asset path escapes sources directory: {asset_id}")
    if target.exists():
        raise FileExistsError(f"Stable source already exists: {target}")

    temp = target.with_name(f".{target.name}.tmp")
    shutil.copy2(source, temp)
    try:
        digest = hashlib.sha256(temp.read_bytes()).hexdigest()
        temp.replace(target)
        assets.append({
            "id": asset_id, "source_name": source.name,
            "stable_path": str(target.relative_to(root.resolve())), "sha256": digest,
        })
        write_json(path, project)
    except Exception:
        temp.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise


def review_mode_for(shot_data: dict) -> str:
    mode = shot_data.get("review_mode", "staged")
    if mode not in ("staged", "fast"):
        raise ValueError(f"Invalid review mode: {mode}")
    return mode


def write_shot_status(root: Path, project: dict, shot_id: str, status: str) -> dict | None:
    schema = project.get("schema_version", 1)
    if schema >= 3:
        path = shot_json_path(root, shot_id)
        shot_data = read_json(path)
        if schema >= 4:
            mode = review_mode_for(shot_data)
            transitions = STAGED_TRANSITIONS if mode == "staged" else FAST_TRANSITIONS
            current = shot_data.get("status")
            if status not in transitions.get(current, set()):
                raise ValueError(f"Invalid {mode} transition: {current} -> {status}")
        shot_data["status"] = status
        write_json(path, shot_data)
        return shot_data
    write_json(legacy_state_path(root, shot_id), {"shot_id": shot_id, "status": status})
    return None


def set_status(root: Path, shot_id: str, status: str, coordinator: bool) -> None:
    path = root / "project.json"
    project = read_json(path)
    shot = find_shot(project, shot_id)
    shot_data = write_shot_status(root, project, shot_id, status)
    if coordinator:
        shot["status"] = status
        if shot_data and project.get("schema_version") >= 4:
            shot["review_mode"] = shot_data["review_mode"]
        write_json(path, project)


def set_review_mode(root: Path, shot_id: str, mode: str, reason: str | None) -> None:
    project_path = root / "project.json"
    project = read_json(project_path)
    if project.get("schema_version") != 4:
        raise ValueError("set-mode requires schema v4; run migrate first")
    shot = find_shot(project, shot_id)
    shot_path = shot_json_path(root, shot_id)
    shot_data = read_json(shot_path)
    if shot_data.get("status") != "todo":
        raise ValueError("Review mode can only change while the shot status is todo")
    reason = reason.strip() if reason else None
    if mode == "fast" and not reason:
        raise ValueError("Fast mode requires the user's explicit request in --reason")
    shot_data["review_mode"] = mode
    shot_data["review_mode_source"] = "explicit_user_request" if reason else "default"
    shot_data["review_mode_reason"] = reason
    shot["review_mode"] = mode
    write_json(shot_path, shot_data)
    write_json(project_path, project)


def approve(root: Path, shot_id: str, stage: str, note: str | None) -> None:
    project_path = root / "project.json"
    project = read_json(project_path)
    if project.get("schema_version") != 4:
        raise ValueError("approve requires schema v4; run migrate first")
    shot = find_shot(project, shot_id)
    shot_path = shot_json_path(root, shot_id)
    shot_data = read_json(shot_path)
    mode = review_mode_for(shot_data)
    transition = APPROVAL_TRANSITIONS[mode].get(stage)
    if not transition:
        raise ValueError(f"Approval stage {stage!r} is not valid for {mode} mode")
    expected, target = transition
    if shot_data.get("status") != expected:
        raise ValueError(f"Cannot approve {stage}: expected {expected}, got {shot_data.get('status')}")
    shot_data.setdefault("approvals", []).append({
        "stage": stage, "decision": "approved", "note": note,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })
    shot_data["status"] = target
    shot["status"] = target
    if (mode == "staged" and stage == "storyboard") or target == "complete":
        shot.setdefault("task", {})["active"] = False
    write_json(shot_path, shot_data)
    write_json(project_path, project)


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
            if schema >= 4:
                shot["review_mode"] = review_mode_for(data)
    write_json(path, project)


def set_concurrency(root: Path, mode: str, pilot_count: int | None = None) -> None:
    path = root / "project.json"
    project = read_json(path)
    if project.get("schema_version") != 4:
        raise ValueError("set-concurrency requires schema v4; run migrate first")
    shots = len(project.get("shots", []))
    active = sum(1 for shot in project.get("shots", []) if shot.get("task", {}).get("active") is True)
    if active:
        raise ValueError("Release active shot tasks before changing the concurrency choice")
    if mode == "all":
        maximum = shots
    elif mode == "pilot":
        if pilot_count not in (1, 2):
            raise ValueError("Pilot mode requires --count 1 or 2")
        maximum = min(pilot_count, shots)
    else:
        raise ValueError("Concurrency mode must be all or pilot")
    workflow = project.setdefault("workflow", {})
    workflow["parallel_launch_mode"] = mode
    workflow["max_parallel_shot_tasks"] = maximum
    write_json(path, project)


def register_task(root: Path, shot_id: str, thread_id: str, host_id: str | None) -> None:
    path = root / "project.json"
    project = read_json(path)
    shot = find_shot(project, shot_id)
    if project.get("schema_version") >= 4:
        if shot.get("status") in {"video_prompt_pending", "video_prompt_review_pending", "complete"}:
            raise ValueError("Shot task cannot be activated during coordinator-owned video-prompt stages")
        workflow = project.get("workflow", {})
        maximum = workflow.get("max_parallel_shot_tasks")
        if workflow.get("parallel_launch_mode") not in {"all", "pilot"} or maximum is None:
            raise ValueError(
                "Concurrency choice is not recorded; ask whether to start all shots or pilot 1-2, "
                "then run set-concurrency"
            )
        active = sum(
            1 for item in project["shots"]
            if item["id"] != shot_id and item.get("task", {}).get("active") is True
        )
        if active >= maximum:
            raise ValueError(f"No shot-task slot available; maximum active tasks is {maximum}")
        shot["task"] = {"thread_id": thread_id, "host_id": host_id, "active": True}
    else:
        shot["task"] = {"thread_id": thread_id, "host_id": host_id}
    write_json(path, project)


def release_task(root: Path, shot_id: str) -> None:
    path = root / "project.json"
    project = read_json(path)
    shot = find_shot(project, shot_id)
    task = shot.setdefault("task", {"thread_id": None, "host_id": None})
    task["active"] = False
    write_json(path, project)


def retry_shot(root: Path, shot_id: str, target: str, reason: str | None) -> None:
    project_path = root / "project.json"
    project = read_json(project_path)
    if project.get("schema_version") != 4:
        raise ValueError("retry requires schema v4; run migrate first")
    reason = reason.strip() if reason else None
    if not reason:
        raise ValueError("Retry requires the user's explicit request in --reason")
    shot = find_shot(project, shot_id)
    shot_path = shot_json_path(root, shot_id)
    data = read_json(shot_path)
    mode = review_mode_for(data)
    allowed = {
        "staged": {"generation_failed": {"storyboard_generating", "video_prompt_pending"}},
        "fast": {"failed": {"running"}},
    }
    current = data.get("status")
    if target not in allowed[mode].get(current, set()):
        raise ValueError(f"Invalid {mode} retry: {current} -> {target}")
    data.setdefault("retries", []).append({
        "from": current, "to": target, "reason": reason,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })
    data["status"] = target
    shot["status"] = target
    write_json(shot_path, data)
    write_json(project_path, project)


STATUS_LABELS = {
    "todo": "未开始", "storyboard_prompt_pending": "提示词待确认",
    "storyboard_generating": "分镜生成中", "storyboard_review_pending": "分镜待确认",
    "video_prompt_pending": "视频提示词待生成", "video_prompt_review_pending": "视频提示词待确认",
    "running": "快速生成中", "review_pending": "完整包待确认",
    "generation_failed": "生成失败", "failed": "生成失败", "complete": "已完成",
}


def dashboard(root: Path) -> str:
    project = read_json(root / "project.json")
    rows = ["| 镜头 | 标题 | 模式 | 当前状态 | 活动任务 |", "|---|---|---|---|---|"]
    for shot in project.get("shots", []):
        shot_path = shot_json_path(root, shot["id"])
        latest = read_json(shot_path) if shot_path.is_file() else shot
        task = shot.get("task", {})
        rows.append(
            f"| {shot['id']} | {shot.get('title', '')} | {latest.get('review_mode', 'legacy')} | "
            f"{STATUS_LABELS.get(latest.get('status'), latest.get('status'))} | "
            f"{'是' if task.get('active') else '否'} |"
        )
    result = "\n".join(rows)
    print(result)
    return result


def task_brief(root: Path, shot_id: str) -> str:
    project = read_json(root / "project.json")
    shot = find_shot(project, shot_id)
    shot_path = shot_json_path(root, shot_id)
    latest = read_json(shot_path) if shot_path.is_file() else shot
    status = latest.get("status")
    if status in {"video_prompt_pending", "video_prompt_review_pending", "complete"}:
        next_step = "此阶段由总控对话负责；不要在镜头任务中生成最终视频提示词。"
    elif status in {"storyboard_review_pending", "review_pending"}:
        next_step = "当前产物正在等待用户审核；停止并等待明确决定。"
    elif status in {"generation_failed", "failed"}:
        next_step = "生成已失败；不要自动重试，停止并等待用户决定。"
    else:
        next_step = "只执行 shot.json 当前状态对应的下一步；完成后更新 shot.json 并停止。"
    root = root.resolve()
    result = (
        f"处理 {shot_id}。\n\n读取：\n"
        f"- {root / 'shared-brief.md'}\n"
        f"- {root / 'shots' / shot_id / 'shot.json'}\n"
        f"- {root / 'project.json'} 中的公共设置\n\n"
        f"{next_step}\n"
        "不要重新解释或复制全局规则。不要自动重试图片生成。"
    )
    print(result)
    return result


def validate_boundaries(defaults: dict) -> list[int | float]:
    if defaults.get("ratio") != "9:16" or defaults.get("layout") != "2x2":
        raise ValueError("Schema v4 requires ratio 9:16 and layout 2x2")
    duration = defaults.get("duration_seconds")
    expected = derive_time_boundaries(duration)
    boundaries = defaults.get("time_boundaries_seconds")
    if boundaries != expected:
        raise ValueError(f"Invalid time boundaries; expected {expected}")
    if defaults.get("time_ranges") != format_time_ranges(expected):
        raise ValueError("time_ranges do not match time_boundaries_seconds")
    return expected


def validate_panels(panels: list, boundaries: list[int | float]) -> None:
    if not panels:
        return
    if len(panels) != 4:
        raise ValueError("Exactly four panel records are required")
    positions = [panel.get("position") for panel in panels]
    if len(set(positions)) != 4 or set(positions) != set(POSITIONS):
        raise ValueError("Panel positions must appear exactly once")
    by_position = {panel["position"]: panel for panel in panels}
    for index, position in enumerate(POSITIONS):
        panel = by_position[position]
        if panel.get("start_seconds") != boundaries[index] or panel.get("end_seconds") != boundaries[index + 1]:
            raise ValueError(f"Panel time mismatch: {position}")
        expected_time = f"{boundaries[index]}–{boundaries[index + 1]}秒"
        if panel.get("time") != expected_time:
            raise ValueError(f"Panel display time mismatch: {position}")


def validate_assets(root: Path, project: dict) -> None:
    assets = project.get("assets", [])
    ids = [asset.get("id") for asset in assets]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate asset IDs")
    sources_dir = (root / "sources").resolve()
    for asset in assets:
        validate_asset_id(asset["id"])
        source = (root / asset["stable_path"]).resolve()
        if not source.is_relative_to(sources_dir):
            raise ValueError(f"Asset path escapes sources directory: {asset['id']}")
        if not source.is_file():
            raise FileNotFoundError(f"Missing stable source: {asset['id']}")
        if hashlib.sha256(source.read_bytes()).hexdigest() != asset["sha256"]:
            raise ValueError(f"Source hash mismatch: {asset['id']}")


def validate_workflow(root: Path, project: dict) -> None:
    workflow = project.get("workflow", {})
    launch_mode = workflow.get("parallel_launch_mode")
    maximum = workflow.get("max_parallel_shot_tasks")
    if launch_mode is None:
        if maximum is not None:
            raise ValueError("Unselected concurrency must not define max_parallel_shot_tasks")
    elif launch_mode in {"all", "pilot"}:
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            raise ValueError("Selected concurrency requires a positive max_parallel_shot_tasks")
        if launch_mode == "all" and maximum != len(project.get("shots", [])):
            raise ValueError("All-shot concurrency must match the project shot count")
        if launch_mode == "pilot" and maximum not in {1, 2}:
            raise ValueError("Pilot concurrency must be one or two shots")
    else:
        raise ValueError("parallel_launch_mode must be null, all, or pilot")
    if workflow.get("retry_policy") != "explicit_user_request_only":
        raise ValueError("Schema v4 requires explicit-user retry policy")
    if workflow.get("video_prompt_owner") != "coordinator":
        raise ValueError("Schema v4 requires coordinator-owned video prompts")
    brief_relative = workflow.get("shared_brief_path")
    if not isinstance(brief_relative, str):
        raise ValueError("Missing shared_brief_path")
    brief = (root / brief_relative).resolve()
    if not brief.is_relative_to(root.resolve()) or not brief.is_file():
        raise ValueError("Invalid or missing shared brief")
    active = sum(1 for shot in project.get("shots", []) if shot.get("task", {}).get("active") is True)
    if launch_mode is None and active:
        raise ValueError("Shot tasks cannot be active before the concurrency choice is recorded")
    if maximum is not None and active > maximum:
        raise ValueError(f"Active shot tasks exceed configured maximum of {maximum}")


def validate(root: Path) -> None:
    project = read_json(root / "project.json")
    schema = project.get("schema_version")
    if schema not in (1, 2, 3, 4):
        raise ValueError("Unsupported schema_version")
    ids = [shot["id"] for shot in project.get("shots", [])]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate shot IDs")
    boundaries = validate_boundaries(project["defaults"]) if schema >= 4 else None
    if schema >= 4:
        validate_workflow(root, project)
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
            if schema >= 4:
                mode = review_mode_for(data)
                if shot.get("review_mode") != mode:
                    raise ValueError(f"Review mode summary mismatch: {shot['id']}")
                valid_mode_statuses = STAGED_TRANSITIONS if mode == "staged" else FAST_TRANSITIONS
                if data.get("status") not in valid_mode_statuses:
                    raise ValueError(f"Status is not valid for {mode} mode: {shot['id']}")
                if not isinstance(data.get("approvals"), list):
                    raise ValueError(f"Invalid approvals: {shot['id']}")
                if not isinstance(data.get("retries"), list):
                    raise ValueError(f"Invalid retries: {shot['id']}")
                if not isinstance(shot.get("task", {}).get("active"), bool):
                    raise ValueError(f"Invalid task activity flag: {shot['id']}")
                validate_panels(data.get("panels", []), boundaries)
        else:
            state_path = legacy_state_path(root, shot["id"])
            if state_path.exists():
                state = read_json(state_path)
                if state.get("shot_id") != shot["id"] or state.get("status") not in STATUSES:
                    raise ValueError(f"Invalid state file: {shot['id']}")
    validate_assets(root, project)
    print(f"OK: schema v{schema}, {len(ids)} shots, {len(project.get('assets', []))} stable sources")


def migrate(root: Path) -> None:
    project_path = root / "project.json"
    backup_path = root / "project.json.bak"
    project = read_json(project_path)
    if project.get("schema_version") == 4:
        raise ValueError("Project is already schema v4")
    if project.get("schema_version") != 3:
        raise ValueError("Automatic migration currently supports schema v3 only")
    if backup_path.exists():
        raise FileExistsError(f"Refusing to overwrite backup: {backup_path}")
    shutil.copy2(project_path, backup_path)
    try:
        defaults = project["defaults"]
        boundaries = derive_time_boundaries(defaults.get("duration_seconds", 5))
        defaults["time_boundaries_seconds"] = boundaries
        defaults["time_ranges"] = format_time_ranges(boundaries)
        project["schema_version"] = 4
        project["workflow"] = {
            "default_review_mode": "staged", "cross_shot_parallel": True,
            "approval": "storyboard_prompt_then_storyboard_then_video_prompt",
            "execution_model": "coordinator_with_shot_slots",
            "parallel_launch_mode": None,
            "max_parallel_shot_tasks": None,
            "shared_brief_path": "shared-brief.md",
            "retry_policy": "explicit_user_request_only",
            "video_prompt_owner": "coordinator",
            "one_visible_task_per_shot": True,
        }
        write_shared_brief(root, project.get("name", "分镜项目"))
        shot_updates = []
        for shot in project["shots"]:
            shot_path = shot_json_path(root, shot["id"])
            data = read_json(shot_path)
            migrated_status = {
                "shot_card_pending": "storyboard_prompt_pending",
                "storyboard_pending": "storyboard_review_pending",
            }.get(data.get("status"), data.get("status"))
            data["status"] = migrated_status
            shot["status"] = migrated_status
            mode = "fast" if data.get("status") in {"running", "review_pending", "failed"} else "staged"
            data.update({
                "review_mode": mode, "review_mode_source": "legacy_inferred",
                "review_mode_reason": None, "approvals": data.get("approvals", []),
                "retries": data.get("retries", []),
            })
            panels = data.get("panels", [])
            if panels:
                if len(panels) != 4 or {panel.get("position") for panel in panels} != set(POSITIONS):
                    raise ValueError(f"Cannot migrate invalid panels: {shot['id']}")
                by_position = {panel["position"]: panel for panel in panels}
                for index, position in enumerate(POSITIONS):
                    panel = by_position[position]
                    panel["start_seconds"] = boundaries[index]
                    panel["end_seconds"] = boundaries[index + 1]
                    panel["time"] = f"{boundaries[index]}–{boundaries[index + 1]}秒"
            shot["review_mode"] = mode
            task = shot.setdefault("task", {"thread_id": None, "host_id": None})
            task["active"] = False
            shot_updates.append((shot_path, data))
        for shot_path, data in shot_updates:
            write_json(shot_path, data)
        write_json(project_path, project)
    except Exception:
        shutil.copy2(backup_path, project_path)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("root", type=Path)
    init.add_argument("--name", required=True)
    init.add_argument("--shots", type=int, required=True)
    init.add_argument("--duration", type=float, default=5)
    source = sub.add_parser("add-source")
    source.add_argument("root", type=Path)
    source.add_argument("source", type=Path)
    source.add_argument("--id", required=True)
    for command in ("status", "shot-status"):
        status = sub.add_parser(command)
        status.add_argument("root", type=Path)
        status.add_argument("shot_id")
        status.add_argument("status", choices=STATUSES)
    mode = sub.add_parser("set-mode")
    mode.add_argument("root", type=Path)
    mode.add_argument("shot_id")
    mode.add_argument("mode", choices=("staged", "fast"))
    mode.add_argument("--reason")
    approval = sub.add_parser("approve")
    approval.add_argument("root", type=Path)
    approval.add_argument("shot_id")
    approval.add_argument("stage", choices=("storyboard_prompt", "storyboard", "video_prompt", "review_package"))
    approval.add_argument("--note")
    sync = sub.add_parser("sync")
    sync.add_argument("root", type=Path)
    concurrency = sub.add_parser("set-concurrency")
    concurrency.add_argument("root", type=Path)
    concurrency.add_argument("mode", choices=("all", "pilot"))
    concurrency.add_argument("--count", type=int)
    task = sub.add_parser("register-task")
    task.add_argument("root", type=Path)
    task.add_argument("shot_id")
    task.add_argument("thread_id")
    task.add_argument("--host-id")
    release = sub.add_parser("release-task")
    release.add_argument("root", type=Path)
    release.add_argument("shot_id")
    retry = sub.add_parser("retry")
    retry.add_argument("root", type=Path)
    retry.add_argument("shot_id")
    retry.add_argument("target", choices=("storyboard_generating", "video_prompt_pending", "running"))
    retry.add_argument("--reason", required=True)
    dashboard_cmd = sub.add_parser("dashboard")
    dashboard_cmd.add_argument("root", type=Path)
    brief = sub.add_parser("task-brief")
    brief.add_argument("root", type=Path)
    brief.add_argument("shot_id")
    check = sub.add_parser("validate")
    check.add_argument("root", type=Path)
    migration = sub.add_parser("migrate")
    migration.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.command == "init":
        init_project(args.root, args.name, args.shots, args.duration)
    elif args.command == "add-source":
        add_source(args.root, args.source, args.id)
    elif args.command == "status":
        set_status(args.root, args.shot_id, args.status, coordinator=True)
    elif args.command == "shot-status":
        set_status(args.root, args.shot_id, args.status, coordinator=False)
    elif args.command == "set-mode":
        set_review_mode(args.root, args.shot_id, args.mode, args.reason)
    elif args.command == "approve":
        approve(args.root, args.shot_id, args.stage, args.note)
    elif args.command == "sync":
        sync_statuses(args.root)
    elif args.command == "set-concurrency":
        set_concurrency(args.root, args.mode, args.count)
    elif args.command == "register-task":
        register_task(args.root, args.shot_id, args.thread_id, args.host_id)
    elif args.command == "release-task":
        release_task(args.root, args.shot_id)
    elif args.command == "retry":
        retry_shot(args.root, args.shot_id, args.target, args.reason)
    elif args.command == "dashboard":
        dashboard(args.root)
    elif args.command == "task-brief":
        task_brief(args.root, args.shot_id)
    elif args.command == "validate":
        validate(args.root)
    elif args.command == "migrate":
        migrate(args.root)


if __name__ == "__main__":
    main()
