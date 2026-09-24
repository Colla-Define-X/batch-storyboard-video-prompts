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
from project_io import atomic_bytes, inside, transaction, consistent_read


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
    "storyboard_review_pending": set(),
    "video_prompt_pending": {"video_prompt_review_pending", "generation_failed"},
    "video_prompt_review_pending": set(),
    "generation_failed": set(),
    "complete": set(),
}
FAST_TRANSITIONS = {
    "todo": {"running"},
    "running": {"review_pending", "failed"},
    "review_pending": set(),
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
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if path.name == "shot.json" and data.get("shot_id") != path.parent.name:
        raise ValueError("shot_id does not match its directory")
    return data


def find_shot(project: dict, shot_id: str) -> dict:
    validate_asset_id(shot_id)
    matches = [shot for shot in project["shots"] if shot["id"] == shot_id]
    if not matches:
        raise KeyError(f"Unknown shot: {shot_id}")
    return matches[0]


def shot_json_path(root: Path, shot_id: str) -> Path:
    validate_asset_id(shot_id)
    directory = inside(root, Path("shots") / shot_id)
    if directory.parent != (root / "shots").resolve() or directory.name != shot_id:
        raise ValueError("Shot path escapes shots directory")
    return inside(root, directory / "shot.json")


def legacy_state_path(root: Path, shot_id: str) -> Path:
    return inside(root, shot_json_path(root, shot_id).parent / "state.json")


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
    if numeric_duration == 4:
        return [0, 1, 2, 3, 4]
    return [normalize_number(numeric_duration * ratio) for ratio in (0, 0.2, 0.5, 0.8, 1)]


def format_time_ranges(boundaries: list[int | float]) -> list[str]:
    return [f"{start}–{end}秒" for start, end in zip(boundaries, boundaries[1:])]


def write_shared_brief(root: Path, name: str) -> None:
    path = root / "shared-brief.md"
    if path.exists():
        return
    path.write_text(
        f"# {name} — 共享视觉规范\n\n"
        "当前对话维护本文件；多任务时由总控维护，镜头任务只读取。\n\n"
        "## 视觉连续性\n\n- 待确认并填写。\n\n"
        "## 产品与包装不变量\n\n- 待确认并填写。\n\n"
        "## 灯光、场景与构图\n\n- 待确认并填写。\n\n"
        "## 声音与交付\n\n- 无对白、无旁白、仅极轻环境声。\n",
        encoding="utf-8",
    )


def init_project(root: Path, name: str, shots: int = 1, duration: float = 4, delivery: str = "storyboard_only") -> None:
    if delivery not in {"storyboard_only", "storyboard_and_video_prompt"}:
        raise ValueError("Invalid delivery scope")
    if isinstance(shots, bool) or not isinstance(shots, int) or shots < 1:
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
        "delivery_scope": delivery,
        "defaults": {
            "ratio": "9:16", "layout": "2x2", "duration_seconds": normalize_number(duration),
            "duration_policy": {"minimum_seconds": 4, "typical_range_seconds": [4, 10]},
            "reading_order": list(POSITIONS),
            "time_boundaries_seconds": boundaries,
            "time_ranges": format_time_ranges(boundaries),
            "video_resolution": "1080p", "audio": "无对白、无旁白、仅极轻环境声",
        },
        "workflow": {
            "default_review_mode": "staged", "cross_shot_parallel": False,
            "approval": "storyboard_prompt_then_storyboard_then_video_prompt",
            "execution_model": "current_conversation",
            "parallel_launch_mode": None,
            "max_parallel_shot_tasks": None,
            "shared_brief_path": "shared-brief.md",
            "retry_policy": "explicit_user_request_only",
            "video_prompt_owner": "current_conversation",
            "one_visible_task_per_shot": False,
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

    sources_dir = inside(root, "sources")
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



def delivery_scope(project: dict) -> str:
    # Older projects explicitly used the combined pipeline.
    value = project.get("delivery_scope", "storyboard_and_video_prompt")
    if value not in {"storyboard_only", "storyboard_and_video_prompt"}:
        raise ValueError("Invalid delivery scope")
    return value


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def file_hash(path: Path, text: bool = False) -> str:
    if not path.is_file() or not path.stat().st_size:
        raise ValueError(f"Missing or empty artifact: {path}")
    if text and not path.read_text(encoding="utf-8").strip():
        raise ValueError(f"Empty text artifact: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_binding(root: Path, project: dict, data: dict) -> dict:
    folder = shot_json_path(root, data["shot_id"]).parent
    validate_boundaries(project["defaults"])
    validate_assets(root, project)
    refs = data.get("references", [])
    assets = {a["id"]: a for a in project.get("assets", [])}
    if not refs or any(r.get("id") not in assets or not r.get("roles") for r in refs):
        raise ValueError("Every shot requires valid reference IDs and roles")
    if len({r["id"] for r in refs}) != len(refs):
        raise ValueError("Duplicate shot references")
    panels = data.get("panels", [])
    if len(panels) != 4:
        raise ValueError("Exactly four panel records are required before generation")
    validate_panels(panels, project["defaults"]["time_boundaries_seconds"])
    if any(not x.get("description", "").strip() or not x.get("label", "").strip() for x in panels):
        raise ValueError("Panels need visible descriptions and labels")
    if data.get("sequence_type") not in {"continuous", "cuts"}:
        raise ValueError("Set sequence_type to continuous or cuts")
    brief = inside(root, project["workflow"]["shared_brief_path"])
    return {
        "prompt": file_hash(inside(root, folder / "storyboard-prompt.md"), text=True),
        "brief": file_hash(brief, text=True),
        "settings": fingerprint({"defaults": project["defaults"], "scope": delivery_scope(project)}),
        "shot": fingerprint({key: data.get(key) for key in ("references", "camera", "must_keep", "forbidden", "sequence_type")}),
        "panels": fingerprint([{k: v for k, v in panel.items() if k != "image"} for panel in panels]),
        "sources": {r["id"]: assets[r["id"]]["sha256"] for r in refs},
    }


def require_approval(data: dict, stage: str, binding: dict) -> None:
    approvals = [a for a in data.get("approvals", []) if a.get("stage") == stage and not a.get("invalidated_at")]
    if not approvals or approvals[-1].get("binding") != binding:
        raise ValueError(f"Missing or stale {stage} approval; use revise and obtain approval")


def check_generation(root: Path, project: dict, data: dict) -> dict:
    binding = input_binding(root, project, data)
    if review_mode_for(data) == "staged":
        require_approval(data, "storyboard_prompt", binding)
    elif not data.get("review_mode_reason") or data.get("review_mode_source") != "explicit_user_request":
        raise ValueError("Fast mode requires explicit authorization")
    return binding


def review_binding(root: Path, project: dict, data: dict) -> dict:
    binding = check_generation(root, project, data)
    if not data.get("generation_claimed"):
        raise ValueError("Run preflight immediately before image generation")
    if data.get("generation_binding") != binding:
        raise ValueError("Generation inputs changed or preflight was not recorded")
    version = data.get("storyboard_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("Set a positive storyboard_version")
    folder = shot_json_path(root, data["shot_id"]).parent
    image = inside(root, folder / f"storyboard-review-v{version:02d}.png")
    verify_image(image)
    from PIL import Image
    with Image.open(image) as im:
        if im.width * 16 != im.height * 9:
            raise ValueError("Storyboard must have a 9:16 canvas")
    if data.get("qa", {}).get("result") not in {"pass", "pass_with_notes"}:
        raise ValueError("Storyboard needs recorded visual QA before review")
    return {"inputs": binding, "version": version, "image": file_hash(image)}


def frozen_binding(root: Path, project: dict, data: dict) -> dict:
    binding = review_binding(root, project, data)
    require_approval(data, "storyboard", binding)
    folder = shot_json_path(root, data["shot_id"]).parent
    if file_hash(inside(root, folder / "storyboard-final.png")) != binding["image"]:
        raise ValueError("Frozen storyboard differs from approved version")
    if read_json(inside(root, folder / "storyboard-final.json")) != binding:
        raise ValueError("Frozen storyboard manifest differs from approval")
    return binding


def video_binding(root: Path, project: dict, data: dict, fast=False) -> dict:
    binding = review_binding(root, project, data) if fast else frozen_binding(root, project, data)
    folder = shot_json_path(root, data["shot_id"]).parent
    return {"storyboard": binding, "video": file_hash(inside(root, folder / "video-prompt.md"), text=True)}


def freeze(root: Path, data: dict, binding: dict) -> None:
    folder = shot_json_path(root, data["shot_id"]).parent
    source = inside(root, folder / f"storyboard-review-v{binding['version']:02d}.png")
    atomic_bytes(inside(root, folder / "storyboard-final.png"), source.read_bytes())
    write_json(inside(root, folder / "storyboard-final.json"), binding)


def preflight(root: Path, shot_id: str) -> None:
    project = read_json(root / "project.json")
    find_shot(project, shot_id)
    data = read_json(shot_json_path(root, shot_id))
    if data.get("status") not in {"storyboard_generating", "running"}:
        raise ValueError("Shot is not authorized to generate")
    binding = check_generation(root, project, data)
    if data.get("generation_binding") != binding:
        raise ValueError("Inputs changed; revise before generating")
    if data.get("generation_claimed"):
        raise ValueError("Generation already claimed; record failure/review and use retry")
    folder = shot_json_path(root, shot_id).parent
    versions = [int(match[1]) for path in folder.glob("storyboard-*.png")
                if (match := re.fullmatch(r"storyboard-(?:review-)?v(\d+)\.png", path.name))]
    previous = data.get("storyboard_version")
    if isinstance(previous, int) and not isinstance(previous, bool) and previous > 0:
        versions.append(previous)
    data["storyboard_version"] = max(versions, default=0) + 1
    data["qa"] = {"result": "not_run", "notes": []}
    data["generation_claimed"] = True
    write_json(shot_json_path(root, shot_id), data)
    print(f"OK: generation authorized; save storyboard-v{data['storyboard_version']:02d}.png and matching review version")


def invalidate(data: dict, stages: set[str]) -> None:
    for approval in data.get("approvals", []):
        if approval.get("stage") in stages and not approval.get("invalidated_at"):
            approval["invalidated_at"] = datetime.now(timezone.utc).isoformat()


def revise(root: Path, shot_id: str, stage: str, reason: str) -> None:
    if not reason or not reason.strip():
        raise ValueError("Revision requires the user's explicit request")
    if stage not in {"storyboard_prompt", "storyboard", "video_prompt"}:
        raise ValueError("Invalid revision stage")
    project = read_json(root / "project.json")
    row = find_shot(project, shot_id)
    path = shot_json_path(root, shot_id)
    data = read_json(path)
    if stage == "storyboard_prompt":
        invalidate(data, {"storyboard_prompt", "storyboard", "video_prompt", "review_package"})
        data["generation_binding"] = None
        data["generation_claimed"] = False
        data["status"] = "todo" if review_mode_for(data) == "fast" else "storyboard_prompt_pending"
    elif stage == "storyboard":
        check_generation(root, project, data)
        invalidate(data, {"storyboard", "video_prompt", "review_package"})
        data["status"] = "running" if review_mode_for(data) == "fast" else "storyboard_generating"
        data["generation_binding"] = check_generation(root, project, data)
        data["generation_claimed"] = False
    else:
        if delivery_scope(project) != "storyboard_and_video_prompt":
            raise ValueError("Video-only revision requires combined delivery")
        if review_mode_for(data) == "fast":
            review_binding(root, project, data)
            invalidate(data, {"review_package"})
            data["status"] = "review_pending"
        else:
            frozen_binding(root, project, data)
            invalidate(data, {"video_prompt"})
            data["status"] = "video_prompt_pending"
    data.setdefault("revisions", []).append({"stage": stage, "reason": reason, "at": datetime.now(timezone.utc).isoformat()})
    row["status"] = data["status"]
    write_json(path, data)
    write_json(root / "project.json", project)


def check_state(root: Path, project: dict, data: dict) -> None:
    status = data["status"]
    if status in {"storyboard_generating", "running", "generation_failed", "failed"}:
        check_generation(root, project, data)
    if status == "storyboard_review_pending":
        review_binding(root, project, data)
    if status == "review_pending":
        if delivery_scope(project) == "storyboard_and_video_prompt":
            video_binding(root, project, data, fast=True)
        else:
            review_binding(root, project, data)
    if status in {"video_prompt_pending", "video_prompt_review_pending"}:
        frozen_binding(root, project, data)
        if status == "video_prompt_review_pending":
            video_binding(root, project, data)
    if status == "complete":
        if review_mode_for(data) == "fast":
            binding = video_binding(root, project, data, fast=True) if delivery_scope(project) == "storyboard_and_video_prompt" else review_binding(root, project, data)
            require_approval(data, "review_package", binding)
            frozen = binding["storyboard"] if "storyboard" in binding else binding
            folder = shot_json_path(root, data["shot_id"]).parent
            if file_hash(inside(root, folder / "storyboard-final.png")) != frozen["image"] or read_json(inside(root, folder / "storyboard-final.json")) != frozen:
                raise ValueError("Frozen storyboard differs from approved package")
        elif delivery_scope(project) == "storyboard_only":
            frozen_binding(root, project, data)
        else:
            require_approval(data, "video_prompt", video_binding(root, project, data))


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
        if status in {"generation_failed", "failed"}:
            shot_data["failed_from"] = shot_data["status"]
        if status == "running":
            shot_data["generation_binding"] = check_generation(root, project, shot_data)
            shot_data["generation_claimed"] = False
        shot_data["status"] = status
        check_state(root, project, shot_data)
        write_json(path, shot_data)
        return shot_data
    write_json(legacy_state_path(root, shot_id), {"shot_id": shot_id, "status": status})
    return None


def set_status(root: Path, shot_id: str, status: str, coordinator: bool) -> None:
    path = root / "project.json"
    project = read_json(path)
    shot = find_shot(project, shot_id)
    shot_data = write_shot_status(root, project, shot_id, status)
    if coordinator or project.get("schema_version") == 4:
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
    if mode not in {"staged", "fast"}:
        raise ValueError("Invalid review mode")
    if shot_data.get("status") not in {"todo", "storyboard_prompt_pending"}:
        raise ValueError("Mode can change only before generation; use revise for later stages")
    if shot_data.get("status") == "storyboard_prompt_pending" and mode == "fast":
        shot_data["status"] = "todo"
        shot["status"] = "todo"
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
    if stage == "storyboard_prompt":
        binding = input_binding(root, project, shot_data)
        shot_data["generation_binding"] = binding
        shot_data["generation_claimed"] = False
    elif stage == "storyboard":
        binding = review_binding(root, project, shot_data)
        freeze(root, shot_data, binding)
        if delivery_scope(project) == "storyboard_only":
            target = "complete"
    elif stage == "video_prompt":
        binding = video_binding(root, project, shot_data)
    else:
        binding = video_binding(root, project, shot_data, fast=True) if delivery_scope(project) == "storyboard_and_video_prompt" else review_binding(root, project, shot_data)
        freeze(root, shot_data, binding.get("storyboard", binding))
    shot_data.setdefault("approvals", []).append({
        "binding": binding,
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
            if schema >= 4:
                check_state(root, project, data)
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
    if shots <= 1:
        raise ValueError("Single storyboard stays in the current conversation")
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
    workflow["execution_model"] = "coordinator_with_shot_slots"
    workflow["cross_shot_parallel"] = True
    workflow["one_visible_task_per_shot"] = True
    workflow["video_prompt_owner"] = "coordinator"
    workflow["parallel_launch_mode"] = mode
    workflow["max_parallel_shot_tasks"] = maximum
    write_json(path, project)


def register_task(root: Path, shot_id: str, thread_id: str, host_id: str | None) -> None:
    path = root / "project.json"
    project = read_json(path)
    shot = find_shot(project, shot_id)
    if not thread_id or not thread_id.strip():
        raise ValueError("Task ID must be nonempty")
    if any(item["id"] != shot_id and item.get("task", {}).get("active") and item["task"].get("thread_id") == thread_id for item in project["shots"]):
        raise ValueError("Task is already assigned to another active shot")
    if len(project.get("shots", [])) <= 1:
        raise ValueError("Single storyboard stays in the current conversation")
    if project.get("schema_version") >= 4:
        latest = read_json(shot_json_path(root, shot_id))
        shot["status"] = latest["status"]
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
        "staged": {
            "generation_failed": {data.get("failed_from")},
            "storyboard_review_pending": {"storyboard_generating"},
            "video_prompt_review_pending": {"video_prompt_pending"},
        },
        "fast": {"failed": {"running"}, "review_pending": {"running"}},
    }
    current = data.get("status")
    if target not in allowed[mode].get(current, set()):
        raise ValueError(f"Invalid {mode} retry: {current} -> {target}")
    data.setdefault("retries", []).append({
        "from": current, "to": target, "reason": reason,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })
    if target in {"storyboard_generating", "running"}:
        data["generation_binding"] = check_generation(root, project, data)
        data["generation_claimed"] = False
        invalidate(data, {"storyboard", "video_prompt", "review_package"})
    else:
        frozen_binding(root, project, data)
        invalidate(data, {"video_prompt"})
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
    if status == "complete":
        next_step = "请求范围已完成；仅按用户新的修改要求继续。"
    elif len(project.get("shots", [])) == 1:
        next_step = "单张分镜在当前对话执行，不创建子任务；遵循当前阶段的审核要求。"
    elif status in {"video_prompt_pending", "video_prompt_review_pending"}:
        next_step = "此阶段由总控对话负责；不要在镜头任务中生成最终视频提示词。"
    elif status in {"storyboard_review_pending", "review_pending"}:
        next_step = "当前产物正在等待用户审核；停止并等待明确决定。"
    elif status in {"generation_failed", "failed"}:
        next_step = "生成已失败；不要自动重试，停止并等待用户决定。"
    else:
        next_step = "只执行当前状态允许的下一步；使用workflow命令更新状态，不手改批准记录。"
    root = root.resolve()
    result = (
        f"处理 {shot_id}。\n\n读取：\n"
        f"- {Path(__file__).resolve().parents[1] / 'SKILL.md'}\n"
        f"- {Path(__file__).resolve().parents[1] / 'references' / 'execution.md'}\n"
        f"- {root / 'shared-brief.md'}\n"
        f"- {root / 'shots' / shot_id / 'shot.json'}\n"
        f"- {root / 'shots' / shot_id / 'storyboard-prompt.md'}（缺失先按模板保存）\n"
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
    derive_time_boundaries(duration)
    boundaries = defaults.get("time_boundaries_seconds")
    if not isinstance(boundaries, list) or len(boundaries) != 5 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in boundaries):
        raise ValueError("Invalid time boundaries")
    if boundaries[0] != 0 or boundaries[-1] != duration or any(a >= b for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("Time boundaries must increase from zero to the approved duration")
    if defaults.get("time_ranges") != format_time_ranges(boundaries):
        raise ValueError("time_ranges do not match time_boundaries_seconds")
    return boundaries


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
    sources_dir = inside(root, "sources")
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
    if workflow.get("video_prompt_owner") not in {"coordinator", "current_conversation"}:
        raise ValueError("Invalid video prompt owner")
    if len(project.get("shots", [])) == 1 and launch_mode is not None:
        raise ValueError("Single storyboard cannot use parallel shot tasks")
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
    delivery_scope(project)
    ids = [shot["id"] for shot in project.get("shots", [])]
    if not ids:
        raise ValueError("Project needs at least one shot")
    for sid in ids:
        shot_json_path(root, sid)
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
                if data["status"] != shot["status"]:
                    raise ValueError("Shot status summary mismatch; run sync")
                check_state(root, project, data)
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
        defaults.setdefault("duration_seconds", 4)
        boundaries = defaults.get("time_boundaries_seconds") or derive_time_boundaries(defaults["duration_seconds"])
        # Preserve valid legacy displayed times when numeric boundaries were absent.
        if "time_boundaries_seconds" not in defaults and defaults.get("time_ranges"):
            parsed = [re.fullmatch(r"([0-9.]+)[–-]([0-9.]+)秒", value) for value in defaults["time_ranges"]]
            if len(parsed) == 4 and all(parsed):
                pairs = [(float(m[1]), float(m[2])) for m in parsed]
                if all(pairs[i][1] == pairs[i+1][0] for i in range(3)):
                    boundaries = [normalize_number(pairs[0][0])] + [normalize_number(pair[1]) for pair in pairs]
        defaults["time_boundaries_seconds"] = boundaries
        defaults["time_ranges"] = format_time_ranges(boundaries)
        validate_boundaries(defaults)
        project["schema_version"] = 4
        project.setdefault("delivery_scope", "storyboard_and_video_prompt")
        project["workflow"] = {
            "default_review_mode": "staged", "cross_shot_parallel": False,
            "approval": "storyboard_prompt_then_storyboard_then_video_prompt",
            "execution_model": "current_conversation",
            "parallel_launch_mode": None,
            "max_parallel_shot_tasks": None,
            "shared_brief_path": "shared-brief.md",
            "retry_policy": "explicit_user_request_only",
            "video_prompt_owner": "current_conversation",
            "one_visible_task_per_shot": False,
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
            data["legacy_status"] = migrated_status
            # Old approvals cannot be bound retroactively to today's files.
            migrated_status = "todo" if migrated_status == "todo" else "storyboard_prompt_pending"
            for approval in data.get("approvals", []):
                approval["invalidated_at"] = datetime.now(timezone.utc).isoformat()
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
            shot_backup = shot_path.with_name("shot.json.bak")
            if shot_backup.exists():
                raise FileExistsError(f"Refusing to overwrite backup: {shot_backup}")
            shutil.copy2(shot_path, shot_backup)
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
    init.add_argument("--shots", type=int, default=1)
    init.add_argument("--delivery", choices=("storyboard_only", "storyboard_and_video_prompt"), default="storyboard_only")
    init.add_argument("--duration", type=float, default=4)
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
    pre = sub.add_parser("preflight")
    pre.add_argument("root", type=Path)
    pre.add_argument("shot_id")
    revision = sub.add_parser("revise")
    revision.add_argument("root", type=Path)
    revision.add_argument("shot_id")
    revision.add_argument("stage", choices=("storyboard_prompt", "storyboard", "video_prompt"))
    revision.add_argument("--reason", required=True)
    args = parser.parse_args()
    if args.command == "init":
        init_project(args.root, args.name, args.shots, args.duration, args.delivery)
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
    elif args.command == "preflight":
        preflight(args.root, args.shot_id)
    elif args.command == "revise":
        revise(args.root, args.shot_id, args.stage, args.reason)
    elif args.command == "migrate":
        migrate(args.root)


# Serialize each complete read/modify/write operation; recover interrupted mutations first.
for _name in ("add_source", "set_status", "set_review_mode", "approve", "sync_statuses", "set_concurrency", "register_task", "release_task", "retry_shot", "revise", "preflight", "migrate"):
    globals()[_name] = transaction(globals()[_name])
for _name in ("validate", "dashboard", "task_brief"):
    globals()[_name] = consistent_read(globals()[_name])

if __name__ == "__main__":
    main()
