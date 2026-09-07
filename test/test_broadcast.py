"""Verify metadata requests without contacting Twitch or reading real credentials."""
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

import stream


def test_broadcast():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        settings = root / "broadcast.json"
        for category, game_id in (("None", "0"), ("Just Chatting", "509658")):
            settings.write_text(json.dumps({"title": "testing", "category": category}))
            replies: list[dict[str, list[dict[str, str]]] | None] = [{"data": [{"id": "123"}]}]
            if game_id != "0":
                replies.append({"data": [{"id": game_id}]})
            replies.append(None)

            def response(request, timeout):
                mock = MagicMock()
                body = replies.pop(0)
                mock.__enter__.return_value.read.return_value = json.dumps(body).encode() if body else b""
                return mock

            with patch.object(stream, "ensure_token"), patch.object(stream, "ROOT", root), patch.object(stream, "urlopen", side_effect=response) as api:
                stream.update_broadcast({"client_id": "test", "access_token": "test"})
                request = api.call_args.args[0]
                assert request.method == "PATCH"
                assert request.full_url.endswith("channels?broadcaster_id=123")
                assert json.loads(request.data) == {"title": "testing", "game_id": game_id}
                assert not replies
            with patch.object(stream, "ensure_token", side_effect=ValueError("Missing authorization")), patch.object(stream, "ROOT", root), patch.object(stream, "urlopen") as api:
                try:
                    stream.update_broadcast({})
                except ValueError:
                    pass
                else:
                    raise AssertionError("Missing credentials should stop the update")
                api.assert_not_called()
    print("Passed: title, category clearing/lookup, and missing authorization.")


if __name__ == "__main__":
    test_broadcast()
