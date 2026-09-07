"""Verify cleanup skips active folders, including ones held by a child process."""
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import stream


def test_cleanup():
    with tempfile.TemporaryDirectory() as directory, patch.object(stream, "ROOT", Path(directory)):
        root = Path(directory)
        with stream.prepared_directory() as (active, fd):
            (active / "video.mp4").write_bytes(b"test")
            stream.cleanup_prepared()
            assert active.exists()
        assert not active.exists()
        stop_code = '''
import stream, signal, sys, time
from pathlib import Path
stream.ROOT = Path(sys.argv[1])
def stop(*args):
    raise KeyboardInterrupt
signal.signal(signal.SIGTERM, stop)
try:
    with stream.prepared_directory() as (folder, fd):
        print(folder, flush=True)
        time.sleep(60)
except KeyboardInterrupt:
    pass
'''
        process = subprocess.Popen([sys.executable, "-c", stop_code, str(root)],
                                   cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, text=True)
        assert process.stdout is not None
        stopped_folder = Path(process.stdout.readline().strip())
        process.terminate()
        process.wait(timeout=5)
        assert not stopped_folder.exists(), "Service stop must clean up immediately"
        child_code = '''
import stream, sys, subprocess, os
from pathlib import Path
stream.ROOT = Path(sys.argv[1])
with stream.prepared_directory() as (folder, fd):
    child = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE, pass_fds=(fd,))
    print(folder, flush=True)
    print(child.pid, flush=True)
    sys.stdin.read()
    os._exit(0)
'''
        parent = subprocess.Popen([sys.executable, "-c", child_code, str(root)],
                                  cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True)
        assert parent.stdout is not None
        folder = Path(parent.stdout.readline().strip())
        parent.stdout.readline()
        stream.cleanup_prepared()
        assert folder.exists()
        # Closing the parent input simulates an abrupt exit; its child also gets EOF.
        parent.communicate(timeout=5)
        import time
        for _ in range(50):
            stream.cleanup_prepared()
            if not folder.exists():
                break
            time.sleep(0.02)
        assert not folder.exists()
        legacy = root / ".prepared-unknown"
        legacy.mkdir()
        stream.cleanup_prepared()
        assert legacy.exists(), "Unmarked folders require a separate in-use check"
    print("Passed: active folders protected, normal cleanup, abandoned folder cleanup.")


if __name__ == "__main__":
    test_cleanup()
