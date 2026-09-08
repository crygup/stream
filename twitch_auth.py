"""One-time Twitch authorization and automatic, securely saved token refresh."""

from contextlib import contextmanager
import fcntl
from getpass import getpass
import json
import os
from pathlib import Path
import secrets
import tempfile
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
REDIRECT = "http://localhost:3000"
SCOPE = "channel:manage:broadcast"


@contextmanager
def locked_config():
    with open(ROOT / ".auth.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield json.loads((ROOT / "config.json").read_text())


def save(config):
    descriptor, name = tempfile.mkstemp(prefix=".auth-", dir=ROOT)
    try:
        with os.fdopen(descriptor, "w") as file:
            json.dump(config, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, ROOT / "config.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)


def exchange(config, **fields):
    if not config.get("client_id") or not config.get("client_secret"):
        raise ValueError(
            "Set client_id and client_secret in config.json, then run twitch_auth.py."
        )
    request = Request(
        "https://id.twitch.tv/oauth2/token",
        data=urlencode(
            {
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                **fields,
            }
        ).encode(),
    )
    try:
        with urlopen(request, timeout=20) as response:
            tokens = json.load(response)
    except HTTPError as error:
        raise ValueError(
            f"Twitch token request failed (HTTP {error.code}). Check app credentials; if authorization was revoked, run twitch_auth.py again."
        ) from None
    config.update(
        access_token=tokens["access_token"], refresh_token=tokens["refresh_token"]
    )
    save(config)


def ensure_token(config, rejected_token=None):
    # Serialize renewals across the streamer and --update-info processes.
    with locked_config() as current:
        token = current.get("access_token", "")
        refresh = bool(rejected_token and token == rejected_token) or not token
        if token and not refresh:
            try:
                request = Request(
                    "https://id.twitch.tv/oauth2/validate",
                    headers={"Authorization": "OAuth " + token},
                )
                with urlopen(request, timeout=20) as response:
                    info = json.load(response)
                if (
                    info["client_id"] != current.get("client_id")
                    or not info.get("user_id")
                    or SCOPE not in info.get("scopes", [])
                ):
                    raise ValueError(
                        "Token has the wrong app/account type or permission. Run twitch_auth.py again."
                    )
                refresh = info.get("expires_in", 0) < 60
            except HTTPError as error:
                if error.code != 401:
                    raise
                refresh = True
        if refresh:
            if not current.get("refresh_token"):
                raise ValueError(
                    "One-time authorization needed: run python3 twitch_auth.py."
                )
            exchange(
                current,
                grant_type="refresh_token",
                refresh_token=current["refresh_token"],
            )
        config.update(current)


def authorize():
    config = json.loads((ROOT / "config.json").read_text())
    if not config.get("client_id") or not config.get("client_secret"):
        raise ValueError("Set client_id and client_secret in config.json first.")
    state = secrets.token_urlsafe(32)
    print("Register http://localhost:3000 as an OAuth Redirect URL in your Twitch app.")
    print("Open this link and authorize your broadcasting account:")
    print(
        "https://id.twitch.tv/oauth2/authorize?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": config["client_id"],
                "redirect_uri": REDIRECT,
                "scope": SCOPE,
                "state": state,
                "force_verify": "true",
            }
        )
    )
    print(
        "The localhost page may fail to load. Copy its full address from your browser."
    )
    callback = urlsplit(getpass("Paste the full redirect URL here (hidden): ").strip())
    query = parse_qs(callback.query)
    if (callback.scheme, callback.netloc, callback.path) not in (
        ("http", "localhost:3000", ""),
        ("http", "localhost:3000", "/"),
    ) or not secrets.compare_digest(query.get("state", [""])[0], state):
        raise ValueError(
            "Redirect URL/state does not match this authorization attempt."
        )
    if "code" not in query:
        raise ValueError("Authorization was not granted. Run this helper again.")
    with locked_config() as current:
        if any(current.get(k) != config.get(k) for k in ("client_id", "client_secret")):
            raise ValueError(
                "App credentials changed during authorization. Run this helper again."
            )
        exchange(
            current,
            grant_type="authorization_code",
            code=query["code"][0],
            redirect_uri=REDIRECT,
        )
    print("Authorization saved privately. Future token renewal is automatic.")


if __name__ == "__main__":
    try:
        authorize()
    except (ValueError, OSError, KeyError) as error:
        print(f"Authorization stopped: {error}")
        raise SystemExit(1)
