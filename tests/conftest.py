from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import madspec_cli as cli

from tests.support import (
    create_step_artifacts as create_step_artifacts_helper,
    fake_download as fake_download_helper,
    git_identity_env as git_identity_env_helper,
    write_concept_markdown as write_concept_markdown_helper,
    write_madspec_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

sys.dont_write_bytecode = True

for pycache_dir in SRC_ROOT.rglob("__pycache__"):
    shutil.rmtree(pycache_dir, ignore_errors=True)


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def invoke_cli(cli_runner: CliRunner):
    def _invoke(args: list[str], **kwargs):
        return cli_runner.invoke(cli.app, args, **kwargs)

    return _invoke


@pytest.fixture()
def make_madspec_project(tmp_path: Path, monkeypatch):
    def _make(*, branch: str = "main", project_path: Path | None = None) -> Path:
        project = project_path or tmp_path
        monkeypatch.chdir(project)
        config_path = project / ".madspec" / "config.json"
        if config_path.exists():
            write_madspec_config(project, branch, phase2_enabled=None)
        else:
            write_madspec_config(project, branch)
        return project

    return _make


@pytest.fixture()
def init_memory_branch(make_madspec_project, invoke_cli):
    def _init(*, branch: str = "main", project_path: Path | None = None) -> Path:
        project = make_madspec_project(branch=branch, project_path=project_path)
        result = invoke_cli(["memory", "init", "--branch", branch])
        assert result.exit_code == 0, result.stdout
        return project

    return _init


@pytest.fixture()
def write_concept_markdown():
    return write_concept_markdown_helper


@pytest.fixture()
def create_step_artifacts():
    return create_step_artifacts_helper


@pytest.fixture()
def write_args_file(tmp_path: Path):
    def _write(name: str, payload: object) -> Path:
        args_file = tmp_path / name
        if isinstance(payload, str):
            args_file.write_text(payload, encoding="utf-8")
        else:
            import json

            args_file.write_text(json.dumps(payload), encoding="utf-8")
        return args_file

    return _write


@pytest.fixture()
def git_identity_env() -> dict[str, str]:
    return git_identity_env_helper()


@pytest.fixture()
def fake_template_download():
    return fake_download_helper
