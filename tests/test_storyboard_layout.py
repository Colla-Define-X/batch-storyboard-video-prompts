from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import storyboard_layout  # noqa: E402


def panel(position: str, index: int, start: int | float, end: int | float) -> dict:
    return {
        "position": position,
        "start_seconds": start,
        "end_seconds": end,
        "time": "legacy-label",
        "label": f"动作{index}",
        "image": f"panels/panel-{index:02d}.png",
    }


class StoryboardLayoutTests(unittest.TestCase):
    def test_manifest_uses_numeric_approved_times(self) -> None:
        boundaries = (0, 2, 4, 6, 8)
        panels = [
            panel(position, index, boundaries[index - 1], boundaries[index])
            for index, position in enumerate(storyboard_layout.POSITIONS, start=1)
        ]

        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "shot.json"
            manifest.write_text(json.dumps({"panels": panels}, ensure_ascii=False), encoding="utf-8")
            paths, labels = storyboard_layout.load_manifest(manifest)

        self.assertEqual(len(paths), 4)
        self.assertEqual(labels, [
            "0–2秒 动作1", "2–4秒 动作2", "4–6秒 动作3", "6–8秒 动作4",
        ])

    def test_manifest_requires_exactly_four_records(self) -> None:
        panels = [
            panel(position, index, index - 1, index)
            for index, position in enumerate(storyboard_layout.POSITIONS, start=1)
        ]
        panels.append(panel("bottom_right", 5, 4, 5))
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "shot.json"
            manifest.write_text(json.dumps({"panels": panels}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly four"):
                storyboard_layout.load_manifest(manifest)

    def test_manifest_rejects_duplicate_position(self) -> None:
        panels = [
            panel("top_left", 1, 0, 1),
            panel("top_right", 2, 1, 2),
            panel("bottom_left", 3, 2, 3),
            panel("bottom_left", 4, 3, 4),
        ]
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "shot.json"
            manifest.write_text(json.dumps({"panels": panels}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "each position exactly once"):
                storyboard_layout.load_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
