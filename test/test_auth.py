"""Offline checks for refresh, token rotation, private persistence and retry."""
import json
from email.message import Message
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs

import stream
import twitch_auth as auth


def response(body):
    result = MagicMock()
    result.__enter__.return_value.read.return_value = json.dumps(body).encode()
    return result


def test_auth():
    with tempfile.TemporaryDirectory() as directory, patch.object(auth, "ROOT", Path(directory)):
        path = Path(directory) / "config.json"
        original = dict(client_id="app", client_secret="secret", access_token="old",
                        refresh_token="old+refresh", stream_key="preserved")
        path.write_text(json.dumps(original))
        expired = HTTPError("https://id.twitch.tv/oauth2/validate", 401, "Expired", Message(), None)
        with patch.object(auth, "urlopen", side_effect=[expired, response({
            "access_token": "new", "refresh_token": "rotated"})]) as requests:
            config = {}
            auth.ensure_token(config)
            fields = parse_qs(requests.call_args.args[0].data.decode())
            assert fields["refresh_token"] == ["old+refresh"]
        saved = json.loads(path.read_text())
        assert saved["access_token"] == "new" and saved["refresh_token"] == "rotated"
        assert saved["stream_key"] == "preserved"
        assert path.stat().st_mode & 0o777 == 0o600
        valid = dict(client_id="app", user_id="123", scopes=[auth.SCOPE], expires_in=3600)
        with patch.object(auth, "urlopen", return_value=response(valid)) as requests:
            auth.ensure_token(config, rejected_token="old")
            assert requests.call_count == 1  # Another process already renewed it.
        with patch.object(auth, "urlopen", side_effect=[expired, HTTPError("url", 400, "Revoked", Message(), None)]):
            try:
                auth.ensure_token(config)
            except ValueError as error:
                assert "run twitch_auth.py again" in str(error)
            else:
                raise AssertionError("Revoked token must require authorization")
        assert json.loads(path.read_text()) == saved
        (Path(directory) / "broadcast.json").write_text('{"title":"testing","category":"None"}')
        with patch.object(stream, "ROOT", Path(directory)), patch.object(stream, "ensure_token") as ensure, patch.object(stream, "urlopen", side_effect=[expired, response({"data":[{"id":"123"}]}), response(None)]) as api:
            stream.update_broadcast(config)
            assert api.call_count == 3 and ensure.call_count == 2
        with patch.object(stream, "ROOT", Path(directory)), patch.object(stream, "ensure_token"), patch.object(stream, "urlopen", side_effect=expired) as api:
            try:
                stream.update_broadcast(config)
            except HTTPError:
                pass
            else:
                raise AssertionError("Repeated rejection must stop")
            assert api.call_count == 2
    print("Passed: expiry refresh, rotation, persistence, concurrent reuse, revocation, bounded API retry.")


if __name__ == "__main__":
    test_auth()
