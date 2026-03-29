from __future__ import annotations

import pytest
import typer

from madspec_cli.shared.cli import command_runner


def test_execute_cli_action_emits_json_without_text(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    payload = {"status": "ok"}

    monkeypatch.setattr(command_runner, "emit_json", lambda value: events.append(("json", value)))
    monkeypatch.setattr(command_runner, "show_banner", lambda: events.append(("banner", None)))

    result = command_runner.execute_cli_action(
        lambda: payload,
        json_output=True,
        text_output=lambda value: events.append(("text", value)),
    )

    assert result == payload
    assert events == [("json", payload)]


def test_execute_cli_action_emits_toon_without_text(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    payload = {"status": "ok"}

    monkeypatch.setattr(command_runner, "emit_toon", lambda value: events.append(("toon", value)))
    monkeypatch.setattr(command_runner, "show_banner", lambda: events.append(("banner", None)))

    result = command_runner.execute_cli_action(
        lambda: payload,
        json_output=False,
        toon_output=True,
        text_output=lambda value: events.append(("text", value)),
    )

    assert result == payload
    assert events == [("toon", payload)]


def test_execute_cli_action_maps_exceptions_to_emit_error(monkeypatch) -> None:
    events: list[tuple[str, object]] = []

    monkeypatch.setattr(
        command_runner,
        "emit_error",
        lambda exc, *, json_output, toon_output=False: events.append(
            ("error", {"message": str(exc), "json": json_output, "toon": toon_output})
        ),
    )

    with pytest.raises(typer.Exit) as exc_info:
        command_runner.execute_cli_action(
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            json_output=True,
            toon_output=True,
        )

    assert exc_info.value.exit_code == 1
    assert events == [("error", {"message": "boom", "json": True, "toon": True})]


def test_execute_cli_action_raises_after_structured_emit_when_should_fail(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    payload = {"valid": False}

    monkeypatch.setattr(command_runner, "emit_json", lambda value: events.append(("json", value)))

    with pytest.raises(typer.Exit) as exc_info:
        command_runner.execute_cli_action(
            lambda: payload,
            json_output=True,
            should_fail=lambda value: not value["valid"],
        )

    assert exc_info.value.exit_code == 1
    assert events == [("json", payload)]
