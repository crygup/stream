#!/usr/bin/env python3
"""Prepare a folder of videos, then broadcast the playlist forever."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import signal
import fcntl
import shutil
from contextlib import contextmanager
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from twitch_auth import ensure_token


def update_broadcast(config):
    settings = json.loads((ROOT / "broadcast.json").read_text())
    title, category = settings["title"], settings["category"]
    if not isinstance(title, str) or not title.strip() or len(title) > 140:
        raise ValueError("Broadcast title must contain 1–140 characters.")
    if category is not None and not isinstance(category, str):
        raise ValueError("Category must be a Twitch category name or None.")
    ensure_token(config)

    def api(path, body=None, retry=True):
        request = Request(
            "https://api.twitch.tv/helix/" + path,
            data=json.dumps(body).encode() if body is not None else None,
            method="PATCH" if body is not None else "GET",
            headers={
                "Client-Id": config["client_id"],
                "Authorization": "Bearer " + config["access_token"],
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                data = response.read()
                return json.loads(data) if data else {}
        except HTTPError as error:
            if error.code != 401 or not retry:
                raise
            ensure_token(config, rejected_token=config["access_token"])
            return api(path, body, retry=False)

    user = api("users")["data"][0]
    game_id = "0"
    if category and category.strip().lower() != "none":
        games = api("games?" + urlencode({"name": category.strip()}))["data"]
        if not games:
            raise ValueError(f"Twitch category not found: {category}")
        game_id = games[0]["id"]
    api(
        "channels?" + urlencode({"broadcaster_id": user["id"]}),
        {"title": title, "game_id": game_id},
    )
    print("Twitch title and category updated.", flush=True)


ROOT = Path(__file__).resolve().parent
EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".ts"}
DEFAULTS = dict(
    ingest_url="rtmp://live.twitch.tv/app",
    width=1920,
    height=1080,
    fps=30,
    video_bitrate_kbps=4500,
    manage_broadcast=False,
)


def optional_broadcast(config):
    if config.get("manage_broadcast", False):
        try:
            update_broadcast(config)
        except (ValueError, OSError, KeyError):
            print(
                "Title/category update unavailable; continuing video playback. Run --update-info for details.",
                flush=True,
            )


def run(args, pass_fds=(), input_frames=None):
    private_values = []
    for argument in args:
        if isinstance(argument, str) and argument.startswith(("rtmp://", "rtmps://")):
            private_values.extend((argument, argument.rsplit("/", 1)[-1]))
    with subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", *args],
        pass_fds=pass_fds,
        stdin=subprocess.PIPE if input_frames is not None else None,
        stderr=subprocess.PIPE,
    ) as process:
        stderr = process.stderr
        assert stderr is not None

        def report_errors():
            for line in stderr:
                line = line.decode(errors="replace")
                for value in private_values:
                    if value:
                        line = line.replace(value, "[redacted]")
                print(line, end="", flush=True)

        reporter = threading.Thread(target=report_errors, daemon=True)
        reporter.start()
        try:
            if input_frames is not None:
                stdin = process.stdin
                assert stdin is not None
                try:
                    for frame in input_frames:
                        stdin.write(frame)
                except BrokenPipeError:
                    pass
                finally:
                    try:
                        stdin.close()
                    except BrokenPipeError:
                        pass
            if process.wait():
                raise subprocess.CalledProcessError(process.returncode, ["ffmpeg"])
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            reporter.join(timeout=2)


def cleanup_prepared():
    for directory in ROOT.glob(".prepared-*"):
        if directory.is_symlink() or not directory.is_dir():
            continue
        try:
            with (directory / ".in-use").open("r") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                shutil.rmtree(directory)
        except FileNotFoundError:
            # Unmarked folders predate locking, or another process removed them.
            continue


@contextmanager
def prepared_directory():
    with tempfile.TemporaryDirectory(prefix=".prepared-", dir=ROOT) as directory:
        # Publish the marker only after locking it, so concurrent cleanup is safe.
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            Path(lock.name).rename(Path(directory) / ".in-use")
            yield Path(directory), lock.fileno()


def selected_videos():
    path = ROOT / "playlist.json"
    toggles = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(toggles, dict) or any(
        type(value) is not bool for value in toggles.values()
    ):
        raise ValueError("playlist.json must map video filenames to true or false.")
    videos = sorted(
        (
            p
            for p in (ROOT / "videos").iterdir()
            if p.is_file()
            and p.suffix.lower() in EXTENSIONS
            and toggles.get(p.name, True)
        ),
        key=lambda p: p.name,
    )
    return videos


def idle_screen(config, preview=False):
    from screensaver import prepare, frames

    fps, bounce, sprites = prepare(config, ROOT)
    width, height, bitrate = (
        config[k] for k in ("width", "height", "video_bitrate_kbps")
    )
    if not preview:
        optional_broadcast(config)
    print(
        f"No enabled videos: screensaver with {len(sprites)} images at {fps} FPS.",
        flush=True,
    )
    output = (
        ["-t", "10", "-y", str(ROOT / "preview.flv")]
        if preview
        else [config["ingest_url"].rstrip("/") + "/" + config["stream_key"].strip()]
    )
    run(
        [
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-video_size",
            f"{width}x{height}",
            "-framerate",
            str(fps),
            "-i",
            "pipe:0",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            f"{bitrate}k",
            "-minrate",
            f"{bitrate}k",
            "-maxrate",
            f"{bitrate}k",
            "-bufsize",
            f"{bitrate * 2}k",
            "-g",
            str(fps * 2),
            "-keyint_min",
            str(fps * 2),
            "-sc_threshold",
            "0",
            "-x264-params",
            "nal-hrd=cbr",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-f",
            "flv",
            *output,
        ],
        input_frames=frames(
            sprites, width, height, fps, bounce, seconds=10 if preview else None
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Save 10 seconds locally instead of broadcasting",
    )
    parser.add_argument(
        "--update-info",
        action="store_true",
        help="Apply broadcast.json without starting a stream",
    )
    args = parser.parse_args()
    if args.preview and args.update_info:
        parser.error("Choose --preview or --update-info, not both.")
    config = DEFAULTS | json.loads((ROOT / "config.json").read_text())
    if args.update_info:
        update_broadcast(config)
        return
    cleanup_prepared()
    videos = selected_videos()
    if not args.preview and not config.get("stream_key", "").strip():
        raise ValueError("Set stream_key in config.json first, or use --preview.")
    width, height, fps, bitrate = (
        config[k] for k in ("width", "height", "fps", "video_bitrate_kbps")
    )
    if (
        any(type(n) is not int or n <= 0 for n in (width, height, fps, bitrate))
        or width % 2
        or height % 2
    ):
        raise ValueError(
            "Video settings must be positive integers; width and height must be even."
        )
    if not videos:
        idle_screen(config, preview=args.preview)
        return
    # Prepare once per run so transitions can share one continuous Twitch connection.
    with prepared_directory() as (prepared, lock_fd):
        for index, video in enumerate(videos):
            print(f"Preparing {index + 1}/{len(videos)}: {video.name}", flush=True)
            probe = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=index",
                    "-of",
                    "csv=p=0",
                    str(video),
                ],
                text=True,
                pass_fds=(lock_fd,),
            )
            inputs = ["-i", str(video)]
            if not probe.strip():
                inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            run(
                [
                    *inputs,
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0" if probe.strip() else "1:a:0",
                    "-vf",
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-pix_fmt",
                    "yuv420p",
                    "-b:v",
                    f"{bitrate}k",
                    "-minrate",
                    f"{bitrate}k",
                    "-maxrate",
                    f"{bitrate}k",
                    "-bufsize",
                    f"{bitrate * 2}k",
                    "-g",
                    str(fps * 2),
                    "-keyint_min",
                    str(fps * 2),
                    "-sc_threshold",
                    "0",
                    "-x264-params",
                    "nal-hrd=cbr",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "160k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-af",
                    "apad",
                    "-shortest",
                    str(prepared / f"{index}.mp4"),
                ],
                pass_fds=(lock_fd,),
            )
        playlist = prepared / "playlist.txt"
        playlist.write_text("".join(f"file '{i}.mp4'\n" for i in range(len(videos))))
        output = (
            ["-t", "10", "-y", str(ROOT / "preview.flv")]
            if args.preview
            else [config["ingest_url"].rstrip("/") + "/" + config["stream_key"].strip()]
        )
        if not args.preview:
            optional_broadcast(config)
        print(
            (
                "Saving preview.flv"
                if args.preview
                else "Streaming playlist on loop. Press Ctrl+C to stop."
            ),
            flush=True,
        )
        run(
            [
                "-re",
                "-stream_loop",
                "-1",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                str(playlist),
                "-c",
                "copy",
                "-f",
                "flv",
                *output,
            ],
            pass_fds=(lock_fd,),
        )


if __name__ == "__main__":

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        # Avoid printing command arguments, which include the private stream key.
        print(
            f"Stopped: {error if not isinstance(error, subprocess.CalledProcessError) else 'FFmpeg/FFprobe failed; see output above.'}"
        )
        raise SystemExit(1)
