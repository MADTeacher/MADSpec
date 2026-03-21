from __future__ import annotations

from madspec_cli.memory.stages.architecture.parsers import parse_endpoint_field_value
from madspec_cli.memory.stages.deploy.state import (
    parse_deployment_unit_value,
    parse_environment_value,
)


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


def test_parse_environment_value_accepts_valid_input() -> None:
    parsed = parse_environment_value("prod::Боевой контур::Высокая доступность и внешние пользователи")

    assert parsed == {
        "name": "prod",
        "purpose": "Боевой контур",
        "notes": "Высокая доступность и внешние пользователи",
    }


def test_parse_deployment_unit_value_accepts_valid_input() -> None:
    parsed = parse_deployment_unit_value(
        "api::service::Docker container::Обслуживает HTTP-запросы и фоновые задачи не выполняет"
    )

    assert parsed == {
        "name": "api",
        "kind": "service",
        "runtime": "Docker container",
        "notes": "Обслуживает HTTP-запросы и фоновые задачи не выполняет",
    }
