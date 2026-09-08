# Twitch video loop

Loop videos on Twitch, or show a screensaver when no videos are enabled.
Requires Linux, Python 3.10+, and FFmpeg/FFprobe with libx264 and librsvg.

## Start

1. Copy `examples/config.json` to `config.json` and enter your Twitch `stream_key`.
2. Put videos in `videos/`; they play in filename order.
3. Install and run:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python stream.py
```

Stop with Ctrl+C. Use `--preview` for a local 10-second preview.

## Configuration

- Set resolution, FPS, and bitrate in `config.json`.
- Copy `examples/playlist.json` to `playlist.json` to enable/disable videos by filename. Unlisted videos are enabled.
- Add multiple GIF, WebP, PNG, or SVG images to `assets/` and list them in `screensaver.images` section in the config file with `true`/`false` toggles.
- `screensaver.bounce` controls collisions (default `true`); `screensaver.fps` controls movement smoothness (1–120, default 60).
- Restart after configuration changes.

## Optional Twitch title and category

1. Copy `examples/broadcast.json` to `broadcast.json` and edit the title/category. Use `null` to clear the category.
2. Add your Twitch application's `client_id` and `client_secret` to `config.json`, with `http://localhost:3000` registered as its OAuth redirect URL.
3. Run `.venv/bin/python twitch_auth.py`, authorize your channel, and paste the redirected URL into the terminal.
4. Set `manage_broadcast` to `true`, or run `.venv/bin/python stream.py --update-info` to update immediately.

Burger artwork: [Twemoji](https://github.com/twitter/twemoji/blob/v14.0.2/assets/svg/1f354.svg), © Twitter and contributors, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); resized and animated.
