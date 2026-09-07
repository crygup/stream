# Twitch video loop

Loop local videos on Twitch. When none are enabled, a burger bounces around a
black screen. Requires Linux, Python 3.10+, and FFmpeg/FFprobe with libx264 and librsvg.

## Start

1. Copy `examples/config.json` to `config.json` and enter your Twitch `stream_key`.
2. Put videos in `videos/`.
3. Run `python3 stream.py`. Stop with Ctrl+C.

Only the stream key is required. Videos play in filename order. Preparation takes
time and disk space; temporary copies are cleaned up automatically.

## Choose videos

Copy `examples/playlist.json` to `playlist.json`. Use exact filenames:
`true` plays, `false` skips. Unlisted videos play by default.
Restart after changes. All disabled means the burger screen.

## Optional title and category

Set these in a copy of `examples/broadcast.json` named `broadcast.json`.
`None` clears the category; otherwise use its exact Twitch name.

To enable automatic updates:

1. Add your Twitch app's `client_id` and `client_secret` to `config.json`.
2. Register `http://localhost:3000` as the app's OAuth redirect URL.
3. Run `python3 twitch_auth.py`, open its link, and authorize your channel.
4. Paste the redirected address into the terminal, even if localhost fails to load.
5. Set `manage_broadcast` to `true` in `config.json`.

Tokens renew automatically. Authorization problems won't stop video playback.
Use `python3 stream.py --update-info` to apply title/category changes immediately.

## Checks

- Local preview: `python3 stream.py --preview` (writes an ignored 10-second video).
- Offline tests: `python3 test/run.py`.

Local configs, credentials, videos, previews, and temporary files are ignored by
Git. Only blank/example configs belong in `examples/`.

Burger artwork: [Twemoji](https://github.com/twitter/twemoji),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See `assets/CREDITS.md`.
