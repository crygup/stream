"""A stream key alone starts either videos or the idle screen, without OAuth."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import stream


def test_optional_auth():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "config.json").write_text(json.dumps({"stream_key": "test-key"}))
        for videos in ([], [root / "video.mp4"]):
            with patch.object(stream, "ROOT", root), patch.object(sys, "argv", ["stream.py"]), patch.object(stream, "selected_videos", return_value=videos), patch.object(stream, "update_broadcast") as api, patch.object(stream, "run") as ffmpeg, patch.object(stream.subprocess, "check_output", return_value=""):
                stream.main()
                api.assert_not_called()
                assert ffmpeg.called
                assert ffmpeg.call_args.args[0][-1] == "rtmp://live.twitch.tv/app/test-key"
        with patch.object(stream, "update_broadcast", side_effect=ValueError("Expired")) as api:
            stream.optional_broadcast({"manage_broadcast": True})
            api.assert_called_once()
    print("Passed: key-only video/idle streaming and optional authentication failures.")
