from __future__ import annotations

from madspec_cli.memory.stages.architecture.parsers import parse_endpoint_field_value


def test_parse_endpoint_field_accepts_response_alias() -> None:
    parsed = parse_endpoint_field_value(
        "get-bot-config::response::is_verified::boolean::required::Bot API verification status"
    )

    assert parsed == {
        "operationId": "get-bot-config",
        "field": {
            "section": "response:200",
            "name": "is_verified",
            "type": "boolean",
            "required": True,
            "description": "Bot API verification status",
        },
    }


def test_parse_endpoint_field_rejects_incomplete_response_status() -> None:
    parsed = parse_endpoint_field_value(
        "get-bot-config::response:::boolean::required::Bot API verification status"
    )

    assert parsed is None
