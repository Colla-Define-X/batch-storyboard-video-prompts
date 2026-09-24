#!/usr/bin/env python3
"""Create a labeled reference contact sheet for one storyboard shot."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from project_io import inside
from workflow import shot_json_path, find_shot, validate_assets


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def parse_ref(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--ref must be IMAGE_ID=ROLE")
    image_id, role = value.split("=", 1)
    return image_id.strip(), role.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("shot_id")
    parser.add_argument("--ref", action="append", type=parse_ref, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    project = json.loads((args.project / "project.json").read_text(encoding="utf-8"))
    find_shot(project, args.shot_id)
    shot_json_path(args.project, args.shot_id)
    validate_assets(args.project, project)
    assets = {item["id"]: item for item in project.get("assets", [])}
    refs = args.ref
    for image_id, _ in refs:
        if image_id not in assets:
            raise KeyError(f"Unknown asset: {image_id}")

    columns = 1 if len(refs) == 1 else 2
    rows = math.ceil(len(refs) / columns)
    card_w, card_h, gap, header_h = 700, 760, 24, 100
    width = columns * card_w + (columns + 1) * gap
    height = header_h + rows * card_h + (rows + 1) * gap
    canvas = Image.new("RGB", (width, height), "#F2E8D5")
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 24), f"{args.shot_id} 参考图预览", font=font(42), fill="#3C2A20")

    for index, (image_id, role) in enumerate(refs):
        row, col = divmod(index, columns)
        x = gap + col * (card_w + gap)
        y = header_h + gap + row * (card_h + gap)
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=22, fill="#FFF9EE", outline="#B89B73", width=3)
        asset_path = inside(args.project, assets[image_id]["stable_path"])
        with Image.open(asset_path) as source:
            preview = ImageOps.contain(source.convert("RGB"), (card_w - 40, card_h - 140), Image.Resampling.LANCZOS)
        px = x + (card_w - preview.width) // 2
        py = y + 20 + (card_h - 140 - preview.height) // 2
        canvas.paste(preview, (px, py))
        draw.text((x + 24, y + card_h - 104), image_id, font=font(32), fill="#2E211A")
        draw.text((x + 24, y + card_h - 60), role, font=font(25), fill="#6B4B36")

    output = args.output or args.project / "shots" / args.shot_id / "reference-preview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Choose a new preview filename: {output}")
    with output.open("xb") as stream:
        canvas.save(stream, format="PNG")
    print(output.resolve())


if __name__ == "__main__":
    main()
