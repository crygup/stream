"""Check playlist toggles without contacting Twitch or changing real videos."""
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import stream


def test_playlist():
    with tempfile.TemporaryDirectory() as directory, patch.object(stream, "ROOT", Path(directory)):
        root = Path(directory)
        videos = root / "videos"
        videos.mkdir()
        for name in ("a.mov", "動画.mp4", "notes.txt"):
            (videos / name).touch()
        config = root / "playlist.json"
        assert [p.name for p in stream.selected_videos()] == ["a.mov", "動画.mp4"]
        config.write_text(json.dumps({"a.mov": False, "動画.mp4": True, "missing.mp4": True}))
        assert [p.name for p in stream.selected_videos()] == ["動画.mp4"]
        (videos / "new.MP4").touch()
        assert [p.name for p in stream.selected_videos()] == ["new.MP4", "動画.mp4"]
        config.write_text(json.dumps({"a.mov": False, "動画.mp4": False, "new.MP4": False}))
        assert stream.selected_videos() == []  # Triggers the idle screen.
        for settings in ({"a.mov": "false"}, [], {"a.mov": 0}):
            config.write_text(json.dumps(settings))
            try:
                stream.selected_videos()
            except ValueError:
                pass
            else:
                raise AssertionError(f"Expected rejection: {settings}")
        assert (videos / "a.mov").exists()
    print("Passed: toggles, ordering, new videos, validation and file preservation.")


if __name__ == "__main__":
    test_playlist()
