"""Render the idle screen offline and verify movement and edge reflection."""
from pathlib import Path
import random
import subprocess
import tempfile
from unittest.mock import patch

import stream


def test_idle():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "assets").symlink_to(stream.ROOT / "assets", target_is_directory=True)
        random.seed(7)
        config = dict(width=160, height=90, fps=10, video_bitrate_kbps=200)
        original_run = stream.run
        with patch.object(stream, "ROOT", root), patch.object(stream, "update_broadcast") as api, patch.object(stream, "run", side_effect=lambda args: original_run([a for a in args if a != "-re"])):
            stream.idle_screen(config, preview=True)
            api.assert_not_called()
        raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(root / "preview.flv"),
                                       "-an", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
        frame_bytes = 160 * 90 * 3
        positions = []
        for offset in range(0, len(raw), frame_bytes):
            frame = raw[offset:offset + frame_bytes]
            points = [i // 3 for i in range(0, len(frame), 3) if frame[i] > 100 and frame[i + 1] > 50]
            assert points, "Burger missing from a frame"
            xs, ys = [i % 160 for i in points], [i // 160 for i in points]
            assert max(xs) - min(xs) >= 5 and max(ys) - min(ys) >= 5, "Burger clipped"
            positions.append((sum(xs) / len(xs), sum(ys) / len(ys)))
        assert len(positions) >= 90
        for axis in (0, 1):
            deltas = [b[axis] - a[axis] for a, b in zip(positions, positions[1:])]
            assert min(deltas) < -0.5 and max(deltas) > 0.5, "No edge reflection"
        audio = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(root / "preview.flv")])
        assert audio.strip() == b"aac"
    print("Passed: visible burger, movement, both edge reflections, AAC audio, no Twitch calls.")


if __name__ == "__main__":
    test_idle()
