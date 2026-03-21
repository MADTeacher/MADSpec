from __future__ import annotations

from pathlib import Path

from madspec_cli.shared.cli.file_input import ArgsFileLifecycle, should_cleanup_args_file


def test_should_cleanup_args_file_accepts_relative_tmp_path(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    (project_path / ".madspec" / ".tmp").mkdir(parents=True)

    assert should_cleanup_args_file(".madspec/.tmp/capture-args.json")


def test_should_cleanup_args_file_accepts_absolute_tmp_path(tmp_path) -> None:
    project_path = tmp_path / "project"
    args_file = project_path / ".madspec" / ".tmp" / "capture-args.json"
    args_file.parent.mkdir(parents=True)

    assert should_cleanup_args_file(str(args_file), project_path=project_path)


def test_should_cleanup_args_file_rejects_external_path(tmp_path) -> None:
    project_path = tmp_path / "project"
    external_file = tmp_path / "capture-args.json"

    assert not should_cleanup_args_file(str(external_file), project_path=project_path)


def test_args_file_lifecycle_cleanup_after_success_only_touches_tmp_scope(tmp_path) -> None:
    project_path = tmp_path / "project"
    args_file = project_path / ".madspec" / ".tmp" / "capture-args.json"
    args_file.parent.mkdir(parents=True)
    args_file.write_text("{}", encoding="utf-8")

    lifecycle = ArgsFileLifecycle.from_path(str(args_file), project_path=project_path)
    lifecycle.cleanup_after_success()

    assert not args_file.exists()


def test_args_file_lifecycle_does_not_delete_external_file(tmp_path) -> None:
    project_path = tmp_path / "project"
    external_file = tmp_path / "capture-args.json"
    external_file.write_text("{}", encoding="utf-8")

    lifecycle = ArgsFileLifecycle.from_path(str(external_file), project_path=project_path)
    lifecycle.cleanup_after_success()

    assert external_file.exists()
