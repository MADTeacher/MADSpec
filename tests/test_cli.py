from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

import madspec_cli as cli
from madspec_cli import initializer
from madspec_cli.memory import append_jsonl, get_memory_paths, make_record


runner = CliRunner()


def _step_status(
    *,
    status: str,
    completed_at: str | None = None,
    tdd_phase: str = "not_started",
    red: list[str] | None = None,
    green: list[str] | None = None,
    refactor_note: str | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "completedAt": completed_at,
        "tddPhase": tdd_phase,
        "redEvidence": red or [],
        "greenEvidence": green or [],
        "refactorNote": refactor_note,
    }


def _step_metadata(kind: str, policy: str, waiver_reason: str | None = None) -> dict[str, object]:
    return {
        "kind": kind,
        "tddPolicy": policy,
        "waiverReason": waiver_reason,
    }


def _fake_download(
    project_path: Path,
    ai_assistant: str,
    is_current_dir: bool,
    verbose: bool = False,
    tracker=None,
    client=None,
    debug: bool = False,
    github_token: str | None = None,
):
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / ".madspec" / "templates").mkdir(parents=True, exist_ok=True)
    (project_path / ".madspec" / "templates" / "project-context-template.md").write_text(
        "# template\n",
        encoding="utf-8",
    )
    (project_path / "README.md").write_text("# demo\n", encoding="utf-8")


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_env() -> dict[str, str]:
    return {
        "GIT_AUTHOR_NAME": "MADSpec Tests",
        "GIT_AUTHOR_EMAIL": "tests@example.com",
        "GIT_COMMITTER_NAME": "MADSpec Tests",
        "GIT_COMMITTER_EMAIL": "tests@example.com",
    }


def test_init_creates_structured_memory_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer, "download_and_extract_template", _fake_download)
    result = runner.invoke(
        cli.app,
        ["init", "demo", "--ai", "cursor-agent", "--no-git"],
    )

    assert result.exit_code == 0, result.stdout
    project_path = tmp_path / "demo"
    paths = get_memory_paths(project_path, "main")
    assert paths["progress"].exists()
    assert paths["active_session"].exists()
    assert (project_path / ".madspec" / "procedures" / "next-step-selection.md").exists()
    assert (project_path / ".madspec" / "main" / "project-context.md").exists()


def test_memory_commands_support_validation_and_retrieve_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert result.exit_code == 0, result.stdout

    paths = get_memory_paths(project_path, "main")
    append_jsonl(
        paths["decision_log"],
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Validated planning decision",
                status="validated",
                evidence=["README.md"],
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )

    promote_result = runner.invoke(
        cli.app,
        ["memory", "promote", "--branch", "main", "--json-output"],
    )
    assert promote_result.exit_code == 0, promote_result.stdout
    promoted_payload = json.loads(promote_result.stdout)
    assert promoted_payload["promoted"]["decision"] == 1

    validate_result = runner.invoke(
        cli.app,
        ["memory", "validate", "--branch", "main", "--json-output"],
    )
    assert validate_result.exit_code == 0, validate_result.stdout
    assert json.loads(validate_result.stdout)["valid"] is True

    retrieve_result = runner.invoke(
        cli.app,
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.plan", "--json-output"],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    payload = json.loads(retrieve_result.stdout)
    assert payload["semantic"]["decisions"][0]["summary"] == "Validated planning decision"

    next_step_candidate = runner.invoke(
        cli.app,
        [
            "memory",
            "next-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--candidate-step",
            "step-02-auth-flow",
            "--depends-on",
            "step-01-bootstrap",
            "--json-output",
        ],
    )
    assert next_step_candidate.exit_code == 1, next_step_candidate.stdout

    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))
    progress["plannedSteps"] = ["step-01-bootstrap", "step-02-auth-flow"]
    progress["completedSteps"] = ["step-01-bootstrap"]
    progress["stepStatus"] = {
        "step-01-bootstrap": _step_status(
            status="completed",
            completed_at="2026-03-10",
            tdd_phase="completed",
            red=["uv run pytest tests/test_bootstrap.py -q"],
            green=["uv run pytest tests/test_bootstrap.py -q"],
            refactor_note="No refactor needed.",
        ),
        "step-02-auth-flow": _step_status(status="planned"),
    }
    progress["stepMetadata"] = {
        "step-01-bootstrap": _step_metadata("code", "required"),
        "step-02-auth-flow": _step_metadata("code", "required"),
    }
    progress["planningMetadata"]["stepDependencies"] = {"step-02-auth-flow": ["step-01-bootstrap"]}
    paths["progress"].write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")

    next_step_select = runner.invoke(
        cli.app,
        ["memory", "next-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"],
    )
    assert next_step_select.exit_code == 0, next_step_select.stdout
    next_step_payload = json.loads(next_step_select.stdout)
    assert next_step_payload["selected_step"] == "step-02-auth-flow"


def test_memory_register_step_updates_progress_and_views(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    (branch_dir / "concept.md").write_text(
        """# Concept

### Приоритет 1
- Authentication: sign in users
- Sessions: keep users logged in

### Приоритет 2
- Profile: edit user profile

### Приоритет 3
- Export: download settings
""",
        encoding="utf-8",
    )

    init_result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    register_result = runner.invoke(
        cli.app,
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-authentication",
            "--step-kind",
            "code",
            "--covers",
            "Authentication",
            "--covers",
            "Profile",
            "--json-output",
        ],
    )
    assert register_result.exit_code == 0, register_result.stdout
    payload = json.loads(register_result.stdout)
    paths = get_memory_paths(project_path, "main")
    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))

    assert payload["accepted"] is True
    assert progress["plannedSteps"] == ["step-01-authentication"]
    assert progress["coversFunctions"]["step-01-authentication"] == {
        "p1": ["Authentication"],
        "p2": ["Profile"],
        "p3": [],
    }
    assert progress["stepMetadata"]["step-01-authentication"] == {
        "kind": "code",
        "tddPolicy": "required",
        "waiverReason": None,
    }
    assert progress["stepStatus"]["step-01-authentication"]["tddPhase"] == "not_started"
    assert progress["planningMetadata"]["progressMetrics"]["overallProgress"] == 55
    assert (project_path / ".madspec" / "main" / "project-context.md").exists()
    assert (project_path / ".madspec" / "main" / "planning-context-cache.md").exists()


def test_memory_checkpoint_updates_memory_and_retrieve_context(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "mvp.concept",
            "--summary",
            "Concept validated for MVP scheduling assistant",
            "--fact",
            "Primary audience: freelancers scheduling appointments",
            "--decision",
            "P1 focuses on appointment booking and reminders",
            "--contract",
            "Booking workflow must keep reminder settings editable",
            "--evidence",
            ".madspec/main/concept.md",
            "--question",
            "Should team bookings be part of MVP?",
            "--pending-action",
            "Proceed to mvp.design",
            "--json-output",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    paths = get_memory_paths(project_path, "main")

    active_session = json.loads(paths["active_session"].read_text(encoding="utf-8"))
    assert active_session["stage"] == "mvp.concept"
    assert active_session["active_goal"] == "Concept validated for MVP scheduling assistant"
    assert active_session["open_questions"] == ["Should team bookings be part of MVP?"]
    assert active_session["pending_actions"] == ["Proceed to mvp.design"]

    retrieve_result = runner.invoke(
        cli.app,
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.concept", "--json-output"],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["active_session"]["stage"] == "mvp.concept"
    assert retrieve_payload["semantic"]["facts"][0]["summary"] == "Primary audience: freelancers scheduling appointments"
    assert retrieve_payload["semantic"]["decisions"][0]["summary"] == "P1 focuses on appointment booking and reminders"
    assert retrieve_payload["semantic"]["contracts"][0]["summary"] == "Booking workflow must keep reminder settings editable"

    project_context = (project_path / ".madspec" / "main" / "project-context.md").read_text(encoding="utf-8")
    assert "Current stage: `mvp.concept`" in project_context
    assert "Active goal: `Concept validated for MVP scheduling assistant`" in project_context


def test_memory_checkpoint_rejects_invalid_stage_and_empty_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".madspec").mkdir()
    (tmp_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    invalid_stage = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--summary",
            "bad",
            "--json-output",
        ],
    )
    assert invalid_stage.exit_code == 1, invalid_stage.stdout

    empty_summary = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "mvp.concept",
            "--summary",
            "",
            "--json-output",
        ],
    )
    assert empty_summary.exit_code == 1, empty_summary.stdout


def test_memory_register_step_requires_waiver_reason_for_waived_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".madspec").mkdir()
    (tmp_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    branch_dir = tmp_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    (branch_dir / "concept.md").write_text(
        """# Concept

### Приоритет 1
- Authentication: sign in users
""",
        encoding="utf-8",
    )

    init_result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    result = runner.invoke(
        cli.app,
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-ui-polish",
            "--step-kind",
            "non-code",
            "--tdd-policy",
            "waived",
            "--covers",
            "Authentication",
            "--json-output",
        ],
    )

    assert result.exit_code == 1, result.stdout
    assert "waiver reason is required" in result.stdout


def test_memory_register_step_accepts_non_code_not_applicable_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".madspec").mkdir()
    (tmp_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    branch_dir = tmp_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    (branch_dir / "concept.md").write_text(
        """# Concept

### Приоритет 1
- Authentication: sign in users
""",
        encoding="utf-8",
    )

    init_result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    result = runner.invoke(
        cli.app,
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-doc-refresh",
            "--step-kind",
            "non-code",
            "--tdd-policy",
            "not-applicable",
            "--json-output",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["stepMetadata"] == {
        "kind": "non-code",
        "tddPolicy": "not-applicable",
        "waiverReason": None,
    }
    assert payload["covers"] == {"p1": [], "p2": [], "p3": []}


def test_memory_register_step_requires_covers_for_code_steps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".madspec").mkdir()
    (tmp_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    branch_dir = tmp_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    (branch_dir / "concept.md").write_text(
        """# Concept

### Приоритет 1
- Authentication: sign in users
""",
        encoding="utf-8",
    )

    init_result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    result = runner.invoke(
        cli.app,
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-authentication",
            "--step-kind",
            "code",
            "--json-output",
        ],
    )

    assert result.exit_code == 1, result.stdout
    assert "code steps must declare at least one covered function" in result.stdout


def test_memory_register_step_rejects_invalid_step_kind_and_tdd_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".madspec").mkdir()
    (tmp_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    branch_dir = tmp_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    (branch_dir / "concept.md").write_text(
        """# Concept

### Приоритет 1
- Authentication: sign in users
""",
        encoding="utf-8",
    )

    init_result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    invalid_kind = runner.invoke(
        cli.app,
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-auth",
            "--step-kind",
            "unknown",
            "--covers",
            "Authentication",
            "--json-output",
        ],
    )
    invalid_policy = runner.invoke(
        cli.app,
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-auth",
            "--step-kind",
            "non-code",
            "--tdd-policy",
            "sometimes",
            "--covers",
            "Authentication",
            "--json-output",
        ],
    )

    assert invalid_kind.exit_code == 1, invalid_kind.stdout
    assert "step kind must be one of" in invalid_kind.stdout
    assert invalid_policy.exit_code == 1, invalid_policy.stdout
    assert "tdd policy must be one of" in invalid_policy.stdout


def test_git_current_branch_uses_config_fallback_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".madspec").mkdir()
    (tmp_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "feature/fallback", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(cli.app, ["git", "current-branch", "--json-output"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload == {"branch": "feature/fallback", "source": "config"}


def test_git_set_branch_and_list_branches_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    main_result = runner.invoke(cli.app, ["git", "set-branch", "main", "--json-output"])
    feature_result = runner.invoke(cli.app, ["git", "set-branch", "feature/new-ui", "--json-output"])
    list_result = runner.invoke(cli.app, ["git", "list-branches", "--json-output"])

    assert main_result.exit_code == 0, main_result.stdout
    assert feature_result.exit_code == 0, feature_result.stdout
    assert list_result.exit_code == 0, list_result.stdout

    feature_payload = json.loads(feature_result.stdout)
    assert feature_payload["branch"] == "feature/new-ui"
    assert (tmp_path / ".madspec" / "feature/new-ui" / "memory" / "progress.json").exists()

    list_payload = json.loads(list_result.stdout)
    branch_names = {branch["name"] for branch in list_payload["branches"]}
    assert {"main", "feature/new-ui"} == branch_names


def test_git_init_create_branch_commit_and_current_branch_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")

    init_result = runner.invoke(
        cli.app,
        ["git", "init", "--json-output"],
        env=_git_env(),
    )

    assert init_result.exit_code == 0, init_result.stdout
    init_payload = json.loads(init_result.stdout)
    assert init_payload["initialized"] is True
    assert init_payload["already_initialized"] is False
    assert (tmp_path / ".gitignore").exists()

    branch_result = runner.invoke(cli.app, ["git", "create-branch", "feature/auth", "--json-output"])
    current_result = runner.invoke(cli.app, ["git", "current-branch", "--json-output"])

    assert branch_result.exit_code == 0, branch_result.stdout
    assert current_result.exit_code == 0, current_result.stdout
    assert json.loads(current_result.stdout) == {"branch": "feature/auth", "source": "git"}

    (tmp_path / "README.md").write_text("# demo\n\nupdated\n", encoding="utf-8")
    commit_result = runner.invoke(
        cli.app,
        ["git", "commit", "--message", "feat: update readme", "--json-output"],
        env=_git_env(),
    )

    assert commit_result.exit_code == 0, commit_result.stdout
    commit_payload = json.loads(commit_result.stdout)
    assert commit_payload["message"] == "feat: update readme"
    assert len(commit_payload["commit_hash"]) == 40
