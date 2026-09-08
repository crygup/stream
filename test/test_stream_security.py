import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stream import run


class StreamSecurityTest(unittest.TestCase):
    def test_ffmpeg_errors_redact_full_url_and_bare_key(self):
        key = "DUMMY_PRIVATE_STREAM_KEY"
        url = "rtmps://example.invalid/app/" + key
        output = io.StringIO()
        with patch("stream.subprocess.Popen") as popen:
            process = popen.return_value.__enter__.return_value
            process.stderr = io.StringIO(f"Could not open {url}\nFailed publishing {key}\n")
            process.wait.return_value = process.returncode = 1
            with contextlib.redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError) as raised:
                run(["-f", "flv", url])
        self.assertNotIn(key, output.getvalue())
        self.assertNotIn(key, str(raised.exception))
        self.assertIn("[redacted]", output.getvalue())


if __name__ == "__main__":
    unittest.main()
