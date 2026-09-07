"""Local integration check: two clips transition and repeat, including silent input."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def test_loop():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        shutil.copy(Path(__file__).resolve().parents[1] / "stream.py", root)
        shutil.copy(Path(__file__).resolve().parents[1] / "twitch_auth.py", root)
        (root / "videos").mkdir()
        (root / "config.json").write_text(json.dumps(dict(
            stream_key="", width=160, height=90, fps=10, video_bitrate_kbps=200)))
        for index, color in enumerate(("red", "blue")):
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            f"color={color}:s=160x90:r=10:d=2", "-c:v", "libx264",
                            str(root / "videos" / f"{index} clip.mp4")], check=True)
        subprocess.run([sys.executable, str(root / "stream.py"), "--preview"], check=True)
        pixels = subprocess.check_output([
            "ffmpeg", "-v", "error", "-i", str(root / "preview.flv"),
            "-vf", "fps=1,scale=1:1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
        frames = [pixels[i:i + 3] for i in range(0, len(pixels), 3)]
        assert len(frames) >= 9, len(frames)
        for second, channel in ((0, 0), (3, 2), (5, 0), (7, 2)):
            assert frames[second][channel] > 180, (second, frames[second])
        audio = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(root / "preview.flv")])
        assert audio.strip() == b"aac", audio
        assert not list(root.glob(".prepared-*"))
    print("Passed: video transitions, playlist repeat, silent audio and cleanup.")


if __name__ == "__main__":
    test_loop()
