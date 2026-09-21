from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import storyboard_layout  # noqa: E402


class StoryboardLayoutTests(unittest.TestCase):
    def test_manifest_uses_approved_custom_times(self) -> None:
        panels = []
        custom_times = ("0–2秒", "2–4秒", "4–6秒", "6–8秒")
        for index, (position, time) in enumerate(zip(storyboard_layout.POSITIONS, custom_times), start=1):
            panels.append({
                "position": position,
                "time": time,
                "label": f"动作{index}",
                "image": f"panels/panel-{index:02d}.png",
            })

        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "shot.json"
            manifest.write_text(json.dumps({"panels": panels}, ensure_ascii=False), encoding="utf-8")
            paths, labels = storyboard_layout.load_manifest(manifest)

        self.assertEqual(len(paths), 4)
        self.assertEqual(labels, [f"{time} 动作{index}" for index, time in enumerate(custom_times, start=1)])

    def test_manifest_requires_exact_positions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "shot.json"
            manifest.write_text(json.dumps({"panels": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                storyboard_layout.load_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
