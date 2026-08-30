from __future__ import annotations

import uuid
from unittest.mock import Mock, patch

from gis.telemetry.cli import parser, run


def test_send_defaults_are_uuid_values() -> None:
    arguments = parser().parse_args(["send", "--write-key", "local-test"])

    assert isinstance(arguments.session_key, uuid.UUID)
    assert isinstance(arguments.event_id, uuid.UUID)


def test_send_serializes_generated_uuid_defaults() -> None:
    response = Mock(ok=True)
    response.json.return_value = {"accepted": 1, "duplicates": 0, "rejected": 0}

    with patch("gis.telemetry.cli.requests.post", return_value=response) as post:
        assert run(["send", "--write-key", "local-test", "--page-path", "/test/"]) == 0

    payload = post.call_args.kwargs["json"]
    assert uuid.UUID(payload["session_key"])
    assert uuid.UUID(payload["events"][0]["event_id"])
