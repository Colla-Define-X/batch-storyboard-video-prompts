#!/usr/bin/env python3
"""Compose a deterministic 9:16 four-panel storyboard from a manifest."""

from __future__ import annotations

import argparse
import json
import io
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont
from project_io import inside


POSITIONS = ("top_left", "top_right", "bottom_left", "bottom_right")
DEFAULT_TIMES = ("0–1秒", "1–2秒", "2–3秒", "3–4秒")


def fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def find_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    candidates: Iterable[Path] = [Path(font_path)] if font_path else [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    raise FileNotFoundError("No Chinese font found; pass --font explicitly")


def compose(panel_paths: list[Path], labels: list[str], output: Path, width: int, height: int,
            divider: int, font_path: str | None) -> None:
    if len(panel_paths) != 4 or len(labels) != 4:
        raise ValueError("Exactly four panels and four labels are required")
    if output.exists():
        raise FileExistsError(f"Choose a new storyboard version: {output}")
    if width < 360 or height < 640 or width * 16 != height * 9 or not 0 <= divider < min(width, height) // 8:
        raise ValueError("Use a 9:16 canvas of at least 360x640 and a narrow nonnegative divider")
    if any(not isinstance(label, str) or not label.strip() for label in labels):
        raise ValueError("Each panel needs a nonempty label")
    cell_w = (width - divider) // 2
    cell_h = (height - divider) // 2
    canvas = Image.new("RGB", (width, height), "#F7F1E3")
    font = find_font(font_path, max(24, width // 28))
    draw = ImageDraw.Draw(canvas)
    # One shared font size keeps all four labels consistent.
    font_size = max(24, width // 28)
    while max(draw.textbbox((0, 0), label, font=font)[2] for label in labels) + 4 * (width // 55) > cell_w:
        font_size -= 1
        if font_size < max(12, width // 70):
            raise ValueError("Labels are too long; shorten them before rendering")
        font = find_font(font_path, font_size)
    coords = ((0, 0), (cell_w + divider, 0), (0, cell_h + divider), (cell_w + divider, cell_h + divider))
    for path, label, (x, y) in zip(panel_paths, labels, coords):
        with Image.open(path) as source:
            panel = fit_cover(source.convert("RGB"), (cell_w, cell_h))
        canvas.paste(panel, (x, y))
        text_box = draw.textbbox((0, 0), label, font=font)
        text_w = text_box[2] - text_box[0]
        text_h = text_box[3] - text_box[1]
        pad_x, pad_y = width // 55, height // 170
        box_w, box_h = text_w + pad_x * 2, text_h + pad_y * 2
        box_x = x + (cell_w - box_w) // 2
        box_y = y + cell_h - box_h - height // 55
        draw.rounded_rectangle((box_x, box_y, box_x + box_w, box_y + box_h), radius=box_h // 2, fill="#FFF8E8")
        draw.text((box_x + pad_x, box_y + pad_y - text_box[1]), label, font=font, fill="#111111")
    output.parent.mkdir(parents=True, exist_ok=True)
    image_format = Image.registered_extensions().get(output.suffix.lower())
    if image_format not in {"PNG", "JPEG", "WEBP"}:
        raise ValueError("Output must be PNG, JPEG, or WebP")
    buffer = io.BytesIO()
    canvas.save(buffer, format=image_format, quality=95)
    with output.open("xb") as stream:
        stream.write(buffer.getvalue())


def load_manifest(path: Path) -> tuple[list[Path], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    panels = data.get("panels", [])
    if not isinstance(panels, list) or len(panels) != 4:
        raise ValueError("Manifest must contain exactly four panel records")
    positions = [item.get("position") for item in panels]
    if len(set(positions)) != 4 or set(positions) != set(POSITIONS):
        raise ValueError(f"Manifest must contain each position exactly once: {', '.join(POSITIONS)}")
    by_position = {item["position"]: item for item in panels}
    paths, labels = [], []
    for position, default_time in zip(POSITIONS, DEFAULT_TIMES):
        item = by_position[position]
        paths.append(inside(path.parent, item["image"]))
        if "start_seconds" in item and "end_seconds" in item:
            time = f"{item['start_seconds']}–{item['end_seconds']}秒"
        else:
            time = item.get("time", default_time)
        labels.append(f"{time} {item['label']}")
    return paths, labels


def split_grid(source: Path, output_dir: Path, version: int, divider: int = 0) -> list[Path]:
    """Split a verified equal 2x2 grid; caller supplies the observed central divider width."""
    if version < 1 or divider < 0:
        raise ValueError("Use a positive version and nonnegative divider")
    paths = [output_dir / f"panel-v{version:02d}-{index:02d}.png" for index in range(1, 5)]
    if any(path.exists() for path in paths):
        raise FileExistsError("Panel version already exists; choose a new version")
    with Image.open(source) as image:
        if divider >= min(image.size) // 8:
            raise ValueError("Divider is too wide")
        left, top = (image.width-divider)//2, (image.height-divider)//2
        right, bottom = (image.width+divider)//2, (image.height+divider)//2
        boxes = [(0,0,left,top),(right,0,image.width,top),(0,bottom,left,image.height),(right,bottom,image.width,image.height)]
        panels = [image.crop(box).convert('RGB') for box in boxes]
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        for panel, path in zip(panels, paths):
            with path.open('xb') as stream:
                written.append(path)
                panel.save(stream, format='PNG')
    except BaseException:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return paths


def main() -> None:
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'split':
        split = argparse.ArgumentParser()
        split.add_argument('source', type=Path)
        split.add_argument('output_dir', type=Path)
        split.add_argument('--version', type=int, required=True)
        split.add_argument('--divider', type=int, default=0)
        args = split.parse_args(sys.argv[2:])
        for path in split_grid(args.source, args.output_dir, args.version, args.divider):
            print(path.resolve())
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, help="shot.json or another four-panel manifest")
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--divider", type=int, default=8)
    parser.add_argument("--font")
    args = parser.parse_args()
    paths, labels = load_manifest(args.manifest)
    compose(paths, labels, args.output, args.width, args.height, args.divider, args.font)


if __name__ == "__main__":
    main()
