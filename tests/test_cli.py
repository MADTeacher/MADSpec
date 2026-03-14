from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

import madspec_cli as cli
from madspec_cli.features.init.infrastructure import initializer_core
from madspec_cli.memory import append_jsonl, get_memory_paths, make_record
from madspec_cli.memory.stages.architecture.parsers import parse_endpoint_field_value


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


def _create_step_artifacts(branch_dir: Path, step_id: str) -> None:
    step_dir = branch_dir / "steps" / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    for file_name in ("description.md", "tasks.md", "tests.md", "validation.md"):
        (step_dir / file_name).write_text(f"# {step_id} {file_name}\n", encoding="utf-8")


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
    monkeypatch.setattr(initializer_core, "download_and_extract_template", _fake_download)
    result = runner.invoke(
        cli.app,
        ["init", "demo", "--ai", "cursor-agent", "--no-git"],
    )

    assert result.exit_code == 0, result.stdout
    project_path = tmp_path / "demo"
    paths = get_memory_paths(project_path, "main")
    assert paths["progress"].exists()
    assert paths["active_session"].exists()
    assert paths["design_state"].exists()
    assert paths["tech_state"].exists()
    assert paths["architecture_state"].exists()
    assert paths["plan_state"].exists()
    assert (project_path / ".madspec" / "procedures" / "next-step-selection.md").exists()
    assert (project_path / ".madspec" / "main" / "project-context.md").exists()
    assert (project_path / ".madspec" / "main" / "implementation-plan.md").exists()


def test_init_accepts_qwen_agent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", _fake_download)
    result = runner.invoke(
        cli.app,
        ["init", "demo", "--ai", "qwen", "--no-git", "--ignore-agent-tools"],
    )

    assert result.exit_code == 0, result.stdout
    assert "Selected AI assistant:" in result.stdout
    assert "qwen" in result.stdout


def test_init_rejects_unknown_agent_and_lists_qwen(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli.app,
        ["init", "demo", "--ai", "unknown-agent", "--no-git"],
    )

    assert result.exit_code == 1
    assert "Invalid AI assistant 'unknown-agent'" in result.stdout
    assert "qwen" in result.stdout


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
    _create_step_artifacts(branch_dir, "step-01-authentication")

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

    capture_result = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "mvp.concept",
            "--project-name",
            "MVP scheduling assistant",
            "--system-overview",
            "System helps freelancers manage bookings and reminders from one interface.",
            "--audience",
            "Freelancers scheduling appointments",
            "--scenario",
            "Create and reschedule appointments from one calendar",
            "--pain",
            "Manual follow-ups cause missed appointments",
            "--feature-p1",
            "Booking workflow::Create bookings and send reminders",
            "--constraint",
            "Reminder settings must stay editable per booking",
            "--next-action",
            "Proceed to mvp.design",
            "--json-output",
        ],
    )
    assert capture_result.exit_code == 0, capture_result.stdout

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
    assert retrieve_payload["artifact_state"]["concept"] is None
    assert retrieve_payload["concept_status"]["is_complete"] is True
    assert retrieve_payload["concept_status"]["missing_required_fields"] == []
    assert retrieve_payload["concept_status"]["filled_fields"] == [
        "projectName",
        "systemOverview",
        "audiences",
        "scenarios",
        "painPoints",
        "features.p1",
        "constraints",
        "nextActions",
        "checkpointSummary",
    ]
    assert retrieve_payload["concept_status"]["counts"] == {
        "audiences": 1,
        "scenarios": 1,
        "pain_points": 1,
        "p1_features": 1,
        "p2_features": 0,
        "p3_features": 0,
        "constraints": 1,
        "assumptions": 0,
        "next_actions": 1,
    }
    assert retrieve_payload["concept_status"]["last_checkpoint_summary"] == "Concept validated for MVP scheduling assistant"
    assert retrieve_payload["semantic"]["contracts"][0]["summary"] == "Reminder settings must stay editable per booking"
    assert retrieve_payload["episodes"] == []
    assert retrieve_payload["decision_log"] == []

    retrieve_full_result = runner.invoke(
        cli.app,
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.concept",
            "--full-artifact",
            "--include-history",
            "--json-output",
        ],
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert retrieve_full_payload["artifact_state"]["concept"]["projectName"] == "MVP scheduling assistant"
    assert retrieve_full_payload["artifact_state"]["concept"]["systemOverview"] == "System helps freelancers manage bookings and reminders from one interface."
    assert retrieve_full_payload["artifact_state"]["concept"]["checkpointSummary"] == "Concept validated for MVP scheduling assistant"
    assert retrieve_full_payload["artifact_state"]["concept"]["features"]["p1"] == [
        {"name": "Booking workflow", "description": "Create bookings and send reminders"}
    ]
    assert retrieve_full_payload["decision_log"] != []

    project_context = (project_path / ".madspec" / "main" / "project-context.md").read_text(encoding="utf-8")
    assert "Current stage: `mvp.concept`" in project_context
    assert "Active goal: `Concept validated for MVP scheduling assistant`" in project_context
    assert "Concept checkpoint summary: `Concept validated for MVP scheduling assistant`" in project_context


def test_memory_capture_supports_incremental_non_iterative_stages(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    capture_result = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "mvp.concept",
            "--summary",
            "Captured discovery notes",
            "--project-name",
            "MVP scheduling assistant",
            "--system-overview",
            "System helps freelancers manage bookings and reminders from one interface.",
            "--audience",
            "Freelancers",
            "--scenario",
            "Book and reschedule client meetings",
            "--pain",
            "Appointments are managed manually across chats and notes",
            "--feature-p1",
            "Booking workflow::Capture booking details and send reminders",
            "--assumption",
            "Users already have repeat clients",
            "--next-action",
            "Proceed to mvp.design",
            "--question",
            "Do we need team scheduling in MVP?",
            "--json-output",
        ],
    )
    assert capture_result.exit_code == 0, capture_result.stdout
    capture_payload = json.loads(capture_result.stdout)
    assert capture_payload["written"]["facts"] == 6
    assert capture_payload["written"]["decisions"] == 1

    retrieve_result = runner.invoke(
        cli.app,
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.concept", "--json-output"],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["active_session"]["open_questions"] == ["Do we need team scheduling in MVP?"]
    assert retrieve_payload["artifact_state"]["concept"] is None
    assert retrieve_payload["concept_status"]["is_complete"] is True
    assert retrieve_payload["concept_status"]["filled_fields"] == [
        "projectName",
        "systemOverview",
        "audiences",
        "scenarios",
        "painPoints",
        "features.p1",
        "assumptions",
        "nextActions",
    ]
    assert retrieve_payload["concept_status"]["counts"] == {
        "audiences": 1,
        "scenarios": 1,
        "pain_points": 1,
        "p1_features": 1,
        "p2_features": 0,
        "p3_features": 0,
        "constraints": 0,
        "assumptions": 1,
        "next_actions": 1,
    }
    assert retrieve_payload["decision_log"] == []

    checkpoint_result = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "mvp.concept",
            "--summary",
            "Concept ratified from accumulated memory",
            "--evidence",
            ".madspec/main/concept.md",
            "--json-output",
        ],
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout
    checkpoint_payload = json.loads(checkpoint_result.stdout)
    assert checkpoint_payload["used_existing_stage_memory"] is True


def test_memory_capture_supports_design_stage_state_and_retrieve(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    branch_name = "main"
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": branch_name, "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    ui_dir = project_path / ".madspec" / branch_name / "ui-prototype"
    ui_dir.mkdir(parents=True)
    for name in ("index.html", "schedule-board.html", "profile-studio.html", "export-hub.html"):
        (ui_dir / name).write_text(f"<html><body>{name}</body></html>\n", encoding="utf-8")

    concept_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.concept",
            "--project-name",
            "MVP scheduling assistant",
            "--system-overview",
            "System helps freelancers manage bookings and reminders from one interface.",
            "--audience",
            "Freelancers",
            "--scenario",
            "Book and reschedule client meetings",
            "--pain",
            "Appointments are managed manually across chats and notes",
            "--feature-p1",
            "Booking workflow::Capture booking details and send reminders",
            "--feature-p2",
            "Profile studio::Customize the public-facing profile",
            "--feature-p3",
            "Export hub::Download settings and summaries",
            "--json-output",
        ],
    )
    assert concept_capture.exit_code == 0, concept_capture.stdout

    design_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.design",
            "--summary",
            "Captured design iteration",
            "--design-overview",
            "A workspace-first web UI with clear transitions between planning, profile tuning, and exports.",
            "--platform",
            "Web",
            "--zone",
            "operations::Operations::Daily scheduling workspace",
            "--zone",
            "settings::Settings::Profile and export configuration",
            "--screen",
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "--screen",
            "profile-studio::Profile studio::settings::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "--screen",
            "export-hub::Export hub::settings::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
            "--screen-feature",
            "schedule-board::p1::Booking workflow",
            "--screen-feature",
            "profile-studio::p2::Profile studio",
            "--screen-feature",
            "export-hub::p3::Export hub",
            "--flow",
            "manage-booking::Manage booking::Create and review a booking flow from one workspace",
            "--flow-step",
            "manage-booking::schedule-board::Create booking::Open booking details with reminders",
            "--flow-step",
            "manage-booking::profile-studio::Review profile::Confirm public profile details",
            "--flow-alternative",
            "manage-booking::Skip profile review when no changes are needed",
            "--nav",
            "schedule-board::profile-studio::Profile settings shortcut",
            "--nav",
            "profile-studio::export-hub::Export settings CTA",
            "--platform-constraint",
            "Primary interactions must remain usable on narrow laptop screens",
            "--screen-data",
            "schedule-board::displayed::Upcoming bookings with reminder state",
            "--screen-data",
            "profile-studio::input::Public display name",
            "--next-action",
            "Review the latest prototype with the user",
            "--json-output",
        ],
    )
    assert design_capture.exit_code == 0, design_capture.stdout

    retrieve_result = runner.invoke(
        cli.app,
        ["memory", "retrieve", "--branch", branch_name, "--stage", "mvp.design", "--json-output"],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["concept_status"] is None
    assert retrieve_payload["design_status"]["is_complete"] is True
    assert retrieve_payload["design_status"]["counts"] == {
        "platforms": 1,
        "zones": 2,
        "screens": 3,
        "flows": 1,
        "navigation_links": 2,
        "platform_constraints": 1,
    }
    assert retrieve_payload["design_status"]["uncovered_features"] == {
        "p1": [],
        "p2": [],
        "p3": [],
    }
    assert retrieve_payload["design_status"]["missing_prototype_files"] == []
    assert retrieve_payload["decision_log"] == []
    assert retrieve_payload["artifact_state"]["design"] is None

    checkpoint_result = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            branch_name,
            "--stage",
            "mvp.design",
            "--summary",
            "Design ratified for prototype review",
            "--evidence",
            ".madspec/main/ui-design.md",
            "--evidence",
            ".madspec/main/ui-prototype/index.html",
            "--json-output",
        ],
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    retrieve_full_result = runner.invoke(
        cli.app,
        [
            "memory",
            "retrieve",
            "--branch",
            branch_name,
            "--stage",
            "mvp.design",
            "--full-artifact",
            "--include-history",
            "--json-output",
        ],
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert retrieve_full_payload["artifact_state"]["design"]["checkpointSummary"] == "Design ratified for prototype review"
    assert retrieve_full_payload["artifact_state"]["design"]["revision"] == 1
    assert retrieve_full_payload["decision_log"] != []
    ui_design = (project_path / ".madspec" / branch_name / "ui-design.md").read_text(encoding="utf-8")
    assert "## Review Journeys" in ui_design
    assert "Storyboard path" in ui_design
    assert "Покрытие функций" not in ui_design


def test_memory_retrieve_returns_tech_status_and_full_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    capture_result = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "mvp.tech",
            "--summary",
            "Captured initial tech direction",
            "--project-type",
            "Web application",
            "--stack-overview",
            "A Python-first stack optimized for rapid MVP delivery and simple deployment.",
            "--requirement",
            "Need web delivery and fast iteration",
            "--preference",
            "Prefer a Python backend and server-rendered UI",
            "--tech-constraint",
            "Hosting must stay simple enough for a single small container",
            "--stack-component",
            "language::Python::3.13::Primary language for backend and tooling",
            "--stack-component",
            "frontend::HTMX::2.x::Keep frontend interactions server-driven and lightweight",
            "--stack-component",
            "backend::FastAPI::0.115::Provide async HTTP APIs with strong typing",
            "--stack-component",
            "database::PostgreSQL::16::Reliable relational storage for bookings and reminders",
            "--stack-component",
            "unit-testing::pytest::8.x::Fast unit and integration test execution",
            "--stack-component",
            "build::Docker::27.x::Standardize local and deployment builds",
            "--library",
            "backend::SQLAlchemy::2.x::ORM and SQL composition",
            "--code-organization",
            "monorepo::feature-first::modular service boundaries::Keep product slices close while preserving clear ownership",
            "--alternative",
            "frontend::React SPA::Too much client complexity for the first MVP iteration",
            "--next-action",
            "Proceed to mvp.architecture",
            "--question",
            "Do we need offline mode?",
            "--json-output",
        ],
    )
    assert capture_result.exit_code == 0, capture_result.stdout

    retrieve_result = runner.invoke(
        cli.app,
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.tech",
            "--limit",
            "1",
            "--json-output",
        ],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["concept_status"] is None
    assert retrieve_payload["tech_status"]["is_complete"] is True
    assert retrieve_payload["tech_status"]["missing_required_fields"] == []
    assert retrieve_payload["tech_status"]["counts"] == {
        "requirements": 1,
        "preferences": 1,
        "constraints": 1,
        "components": 6,
        "libraries": 1,
        "alternatives": 1,
        "next_actions": 1,
    }
    assert retrieve_payload["tech_status"]["selected_slots"] == [
        "backend",
        "build",
        "database",
        "frontend",
        "language",
        "unit-testing",
    ]
    assert retrieve_payload["decision_log"] == []
    assert retrieve_payload["artifact_state"]["tech"] is None

    checkpoint_result = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "mvp.tech",
            "--summary",
            "Tech stack ratified for MVP architecture",
            "--evidence",
            ".madspec/main/tech-stack.md",
            "--json-output",
        ],
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    retrieve_full_result = runner.invoke(
        cli.app,
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.tech",
            "--full-artifact",
            "--include-history",
            "--json-output",
        ],
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert retrieve_full_payload["artifact_state"]["tech"]["projectType"] == "Web application"
    assert retrieve_full_payload["artifact_state"]["tech"]["checkpointSummary"] == "Tech stack ratified for MVP architecture"
    assert retrieve_full_payload["artifact_state"]["tech"]["revision"] == 1
    assert retrieve_full_payload["decision_log"] != []

    tech_stack = (project_path / ".madspec" / "main" / "tech-stack.md").read_text(encoding="utf-8")
    assert "A Python-first stack optimized for rapid MVP delivery and simple deployment." in tech_stack
    assert "FastAPI" in tech_stack


def test_memory_capture_supports_architecture_stage_state_and_retrieve(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    branch_name = "main"
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": branch_name, "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    ui_dir = project_path / ".madspec" / branch_name / "ui-prototype"
    ui_dir.mkdir(parents=True)
    for name in ("index.html", "schedule-board.html", "profile-studio.html", "export-hub.html"):
        (ui_dir / name).write_text(f"<html><body>{name}</body></html>\n", encoding="utf-8")

    concept_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.concept",
            "--project-name",
            "MVP scheduling assistant",
            "--system-overview",
            "System helps freelancers manage bookings and reminders from one interface.",
            "--audience",
            "Freelancers",
            "--scenario",
            "Book and reschedule client meetings",
            "--pain",
            "Appointments are managed manually across chats and notes",
            "--feature-p1",
            "Booking workflow::Capture booking details and send reminders",
            "--feature-p2",
            "Profile studio::Customize the public-facing profile",
            "--feature-p3",
            "Export hub::Download settings and summaries",
            "--json-output",
        ],
    )
    assert concept_capture.exit_code == 0, concept_capture.stdout

    design_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.design",
            "--design-overview",
            "A workspace-first web UI with clear transitions between planning, profile tuning, and exports.",
            "--platform",
            "Web",
            "--zone",
            "operations::Operations::Daily scheduling workspace",
            "--zone",
            "settings::Settings::Profile and export configuration",
            "--screen",
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/schedule-board.html::Shows upcoming bookings and reminder actions",
            "--screen",
            "profile-studio::Profile studio::settings::.madspec/main/ui-prototype/profile-studio.html::Lets the user customize profile details",
            "--screen",
            "export-hub::Export hub::settings::.madspec/main/ui-prototype/export-hub.html::Lets the user export summaries and settings",
            "--screen-feature",
            "schedule-board::p1::Booking workflow",
            "--screen-feature",
            "profile-studio::p2::Profile studio",
            "--screen-feature",
            "export-hub::p3::Export hub",
            "--flow",
            "manage-booking::Manage booking::Create and review a booking flow from one workspace",
            "--flow-step",
            "manage-booking::schedule-board::Create booking::Open booking details with reminders",
            "--flow-step",
            "manage-booking::profile-studio::Review profile::Confirm public profile details",
            "--flow-step",
            "manage-booking::export-hub::Export summary::Download account summary",
            "--nav",
            "schedule-board::profile-studio::Profile settings shortcut",
            "--nav",
            "profile-studio::export-hub::Export settings CTA",
            "--screen-data",
            "schedule-board::displayed::Upcoming bookings with reminder state",
            "--screen-data",
            "schedule-board::input::Reminder lead time",
            "--screen-data",
            "profile-studio::input::Public display name",
            "--screen-data",
            "export-hub::displayed::Export download url",
            "--json-output",
        ],
    )
    assert design_capture.exit_code == 0, design_capture.stdout

    architecture_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.architecture",
            "--summary",
            "Captured architecture iteration",
            "--architecture-overview",
            "A modular web architecture centered on scheduling workflows and server-driven UI contracts.",
            "--project-structure",
            "feature-first::Keep booking flows, profile tuning, and exports isolated by capability",
            "--directory",
            "src/features/scheduling::Booking workflow handlers and orchestration",
            "--directory",
            "src/features/profile::Profile editing logic",
            "--directory",
            "src/features/exports::Export generation handlers",
            "--entity",
            "Booking::Customer booking and reminder configuration",
            "--entity-field",
            "Booking::id::uuid::required::Primary booking identifier",
            "--entity-field",
            "Booking::reminder lead time::integer::required::Reminder lead time in minutes",
            "--entity",
            "Profile::Public profile settings",
            "--entity-field",
            "Profile::public display name::string::required::Display name shown to customers",
            "--entity",
            "ExportJob::Generated export package",
            "--entity-field",
            "ExportJob::download url::string::required::Download location for generated export",
            "--entity-relationship",
            "Booking::Profile::belongs-to::Bookings are owned by the freelancer profile",
            "--entity-state",
            "ExportJob::ready::Export package is ready for download",
            "--endpoint",
            "update-booking-reminder::PUT::/bookings/{id}/reminder::Update booking reminder configuration",
            "--endpoint-screen",
            "update-booking-reminder::schedule-board",
            "--endpoint-field",
            "update-booking-reminder::path::id::uuid::required::Booking identifier",
            "--endpoint-field",
            "update-booking-reminder::request::Reminder lead time::integer::required::Reminder lead time in minutes",
            "--endpoint-field",
            "update-booking-reminder::response:200::Upcoming bookings with reminder state::array::required::Updated booking cards with reminder state",
            "--endpoint",
            "update-profile::PUT::/profile::Update freelancer profile settings",
            "--endpoint-screen",
            "update-profile::profile-studio",
            "--endpoint-field",
            "update-profile::request::Public display name::string::required::Updated public display name",
            "--endpoint-field",
            "update-profile::response:200::profile status::string::required::Profile save status",
            "--endpoint",
            "download-export::GET::/exports/latest::Fetch the latest export package",
            "--endpoint-screen",
            "download-export::export-hub",
            "--endpoint-field",
            "download-export::response:200::Export download url::string::required::Download URL for latest export",
            "--endpoint-error",
            "download-export::404::export_not_ready::Export package is not ready yet",
            "--integration",
            "Email provider::external-api::Deliver reminders to customers::schedule-board|background worker",
            "--code-principle",
            "Keep HTTP handlers thin and move workflow rules into feature services.",
            "--pattern",
            "Repository::Isolate persistence details from feature logic",
            "--security-note",
            "Authorize profile and booking mutations against the current freelancer account.",
            "--performance-note",
            "Reuse precomputed export metadata to avoid rebuilding the package on every download request.",
            "--next-action",
            "Proceed to mvp.plan",
            "--json-output",
        ],
    )
    assert architecture_capture.exit_code == 0, architecture_capture.stdout

    retrieve_result = runner.invoke(
        cli.app,
        ["memory", "retrieve", "--branch", branch_name, "--stage", "mvp.architecture", "--json-output"],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["architecture_status"]["is_complete"] is True
    assert retrieve_payload["architecture_status"]["counts"] == {
        "directories": 3,
        "entities": 3,
        "endpoints": 3,
        "integrations": 1,
        "code_principles": 1,
        "patterns": 1,
    }
    assert retrieve_payload["artifact_state"]["architecture"] is None

    checkpoint_result = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            branch_name,
            "--stage",
            "mvp.architecture",
            "--summary",
            "Architecture ratified for implementation planning",
            "--evidence",
            ".madspec/main/architecture.md",
            "--evidence",
            ".madspec/main/data-model.md",
            "--evidence",
            ".madspec/main/contracts/openapi.yaml",
            "--json-output",
        ],
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    retrieve_full_result = runner.invoke(
        cli.app,
        [
            "memory",
            "retrieve",
            "--branch",
            branch_name,
            "--stage",
            "mvp.architecture",
            "--full-artifact",
            "--include-history",
            "--json-output",
        ],
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert retrieve_full_payload["artifact_state"]["architecture"]["checkpointSummary"] == "Architecture ratified for implementation planning"
    assert retrieve_full_payload["artifact_state"]["architecture"]["revision"] == 1
    assert retrieve_full_payload["decision_log"] != []

    architecture_doc = (project_path / ".madspec" / "main" / "architecture.md").read_text(encoding="utf-8")
    data_model_doc = (project_path / ".madspec" / "main" / "data-model.md").read_text(encoding="utf-8")
    openapi_doc = (project_path / ".madspec" / "main" / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
    assert "A modular web architecture centered on scheduling workflows" in architecture_doc
    assert "Booking" in data_model_doc
    assert "update-booking-reminder" in openapi_doc


def test_memory_capture_and_checkpoint_support_review_and_security(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    review_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "review",
            "--summary",
            "Captured review findings",
            "--fact",
            "Architecture matches the chosen stack",
            "--decision",
            "Refactor auth service boundaries before scaling",
            "--pending-action",
            "Create follow-up refactor task",
            "--json-output",
        ],
    )
    assert review_capture.exit_code == 0, review_capture.stdout

    security_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "security",
            "--summary",
            "Captured security findings",
            "--fact",
            "No rate limiting on login endpoint",
            "--contract",
            "Reset tokens expire within 15 minutes",
            "--json-output",
        ],
    )
    assert security_capture.exit_code == 0, security_capture.stdout

    review_checkpoint = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "review",
            "--summary",
            "Review ratified",
            "--json-output",
        ],
    )
    assert review_checkpoint.exit_code == 0, review_checkpoint.stdout

    security_checkpoint = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "security",
            "--summary",
            "Security audit ratified",
            "--json-output",
        ],
    )
    assert security_checkpoint.exit_code == 0, security_checkpoint.stdout

    review_view = (project_path / ".madspec" / "main" / "review.md").read_text(encoding="utf-8")
    security_view = (project_path / ".madspec" / "main" / "security-audit.md").read_text(encoding="utf-8")
    assert "Refactor auth service boundaries before scaling" in review_view
    assert "No rate limiting on login endpoint" in security_view


def test_memory_checkpoint_rejects_incomplete_tech_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    capture_result = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "mvp.tech",
            "--project-type",
            "API service",
            "--json-output",
        ],
    )
    assert capture_result.exit_code == 0, capture_result.stdout

    checkpoint_result = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "mvp.tech",
            "--summary",
            "Attempt to ratify incomplete tech stack",
            "--evidence",
            ".madspec/main/tech-stack.md",
            "--json-output",
        ],
    )
    assert checkpoint_result.exit_code == 1, checkpoint_result.stdout
    payload = json.loads(checkpoint_result.stdout)
    assert payload["accepted"] is False
    assert "tech state must include a stack overview before checkpoint" in payload["errors"]


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
    _create_step_artifacts(branch_dir, "step-01-doc-refresh")

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
    _create_step_artifacts(branch_dir, "step-01-doc-refresh")

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


def test_memory_register_step_rolls_back_when_step_artifacts_are_missing(tmp_path: Path, monkeypatch) -> None:
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
            "--covers",
            "Authentication",
            "--json-output",
        ],
    )

    paths = get_memory_paths(tmp_path, "main")
    progress = json.loads(paths["progress"].read_text(encoding="utf-8"))
    plan_state = json.loads(paths["plan_state"].read_text(encoding="utf-8"))

    assert result.exit_code == 1, result.stdout
    assert progress["plannedSteps"] == []
    assert plan_state["stepCatalog"] == []


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


def test_memory_implementation_commands_drive_step_lifecycle(tmp_path: Path, monkeypatch) -> None:
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
""",
        encoding="utf-8",
    )

    init_result = runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout
    _create_step_artifacts(branch_dir, "step-01-authentication")

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
            "--json-output",
        ],
    )
    assert register_result.exit_code == 0, register_result.stdout

    start_result = runner.invoke(
        cli.app,
        ["memory", "start-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"],
    )
    assert start_result.exit_code == 0, start_result.stdout
    assert json.loads(start_result.stdout)["step_id"] == "step-01-authentication"

    red_result = runner.invoke(
        cli.app,
        [
            "memory",
            "checkpoint-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--tdd-phase",
            "red",
            "--summary",
            "Auth test is red",
            "--red-evidence",
            "uv run pytest tests/test_auth.py -q",
            "--json-output",
        ],
    )
    assert red_result.exit_code == 0, red_result.stdout

    complete_result = runner.invoke(
        cli.app,
        [
            "memory",
            "complete-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--summary",
            "Authentication implemented",
            "--green-evidence",
            "uv run pytest tests/test_auth.py -q",
            "--refactor-note",
            "No refactor needed.",
            "--fact",
            "Authentication persists session data",
            "--json-output",
        ],
    )
    assert complete_result.exit_code == 0, complete_result.stdout
    complete_payload = json.loads(complete_result.stdout)
    assert complete_payload["written"]["facts"] == 1

    retrieve_result = runner.invoke(
        cli.app,
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--json-output",
        ],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["step"]["status"]["status"] == "completed"
    assert retrieve_payload["step"]["status"]["tddPhase"] == "completed"
    assert retrieve_payload["semantic"]["facts"][0]["summary"] == "Authentication persists session data"


def test_memory_capture_architecture_accepts_response_alias_and_cleans_reject_message(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    branch_name = "main"
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": branch_name, "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    init_result = runner.invoke(cli.app, ["memory", "init", "--branch", branch_name])
    assert init_result.exit_code == 0, init_result.stdout

    ui_dir = project_path / ".madspec" / branch_name / "ui-prototype"
    ui_dir.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "workspace-main.html", "publish-log.html"):
        (ui_dir / name).write_text(f"<html><body>{name}</body></html>\n", encoding="utf-8")

    concept_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.concept",
            "--project-name",
            "Telegram CRM",
            "--system-overview",
            "Manage bot settings, posts, and publish events from one workspace.",
            "--audience",
            "Content managers",
            "--scenario",
            "Review post content and publish it to Telegram channels",
            "--pain",
            "Telegram publishing is fragmented across manual tools",
            "--feature-p1",
            "Bot connection::Configure the bot token and channel",
            "--feature-p2",
            "Workspace::Create and edit posts",
            "--feature-p3",
            "Publish log::Review publish attempts",
            "--json-output",
        ],
    )
    assert concept_capture.exit_code == 0, concept_capture.stdout

    design_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.design",
            "--design-overview",
            "A workspace-first Telegram publishing UI.",
            "--platform",
            "Web",
            "--zone",
            "settings::Settings::Bot setup and verification",
            "--zone",
            "operations::Operations::Post editing and monitoring",
            "--screen",
            "bot-connection::Bot connection::settings::.madspec/main/ui-prototype/index.html::Configure bot token and target channel",
            "--screen",
            "workspace-main::Workspace main::operations::.madspec/main/ui-prototype/workspace-main.html::Edit and preview a post",
            "--screen",
            "publish-log::Publish log::operations::.madspec/main/ui-prototype/publish-log.html::Inspect publish attempts",
            "--screen-feature",
            "bot-connection::p1::Bot connection",
            "--screen-feature",
            "workspace-main::p2::Workspace",
            "--screen-feature",
            "publish-log::p3::Publish log",
            "--flow",
            "publish-post::Publish post::Prepare and send a post to Telegram",
            "--flow-step",
            "publish-post::bot-connection::Verify bot::Confirm Telegram access works",
            "--flow-step",
            "publish-post::workspace-main::Edit post::Prepare post content for sending",
            "--flow-step",
            "publish-post::publish-log::Review log::Inspect the publish attempt result",
            "--screen-data",
            "bot-connection::displayed::is_verified",
            "--screen-data",
            "workspace-main::displayed::post-core",
            "--screen-data",
            "publish-log::displayed::publish-events",
            "--screen-data",
            "workspace-main::input::content_blocks",
            "--json-output",
        ],
    )
    assert design_capture.exit_code == 0, design_capture.stdout

    architecture_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.architecture",
            "--architecture-overview",
            "Backend-first Telegram publishing architecture with feature-first modules.",
            "--project-structure",
            "feature-first::Keep bot-connection, workspace, and publish-log isolated by capability",
            "--directory",
            "src/features/bot-connection::Bot setup and verification logic",
            "--directory",
            "src/features/workspace::Post editing and publishing logic",
            "--directory",
            "src/features/publish-log::Publish attempt history",
            "--entity",
            "Post::Draft or published content item",
            "--entity-field",
            "Post::id::uuid::required::Primary post identifier",
            "--entity-field",
            "Post::content_blocks::json::required::Structured post content",
            "--entity",
            "PublishEvent::Attempt to publish a post",
            "--entity-field",
            "PublishEvent::id::uuid::required::Primary event identifier",
            "--entity-field",
            "PublishEvent::status::string::required::Latest publish attempt status",
            "--endpoint",
            "getBotConfig::GET::/api/bot-config::Load current bot settings",
            "--endpoint-screen",
            "getBotConfig::bot-connection",
            "--endpoint-field",
            "getBotConfig::response::is_verified::boolean::required::Bot API verification status",
            "--endpoint",
            "getPost::GET::/api/posts/{post_id}::Load a post for editing",
            "--endpoint-screen",
            "getPost::workspace-main",
            "--endpoint-field",
            "getPost::path::post_id::uuid::required::Post identifier",
            "--endpoint-field",
            "getPost::request::content_blocks::json::required::Structured post content",
            "--endpoint-field",
            "getPost::response::post-core::object::required::Core post data for the editor and preview",
            "--endpoint",
            "listPublishEvents::GET::/api/publish-log::Load publish history",
            "--endpoint-screen",
            "listPublishEvents::publish-log",
            "--endpoint-field",
            "listPublishEvents::response::publish-events::array::required::Chronological list of publish attempts",
            "--code-principle",
            "Keep HTTP handlers thin and move Telegram rules into feature services.",
            "--json-output",
        ],
    )
    assert architecture_capture.exit_code == 0, architecture_capture.stdout

    retrieve_result = runner.invoke(
        cli.app,
        ["memory", "retrieve", "--branch", branch_name, "--stage", "mvp.architecture", "--json-output"],
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["architecture_status"]["missing_required_fields"] == []
    assert retrieve_payload["architecture_status"]["reference_errors"] == []
    assert retrieve_payload["architecture_status"]["is_complete"] is True

    rejected_capture = runner.invoke(
        cli.app,
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.architecture",
            "--project-structure",
            "backend-first mono-repo without separator",
        ],
    )
    assert rejected_capture.exit_code == 1, rejected_capture.stdout
    assert "Capture rejected. Fix the validation errors below." in rejected_capture.stdout
    assert "Allowed stages:" not in rejected_capture.stdout
    assert "project-structure must use '<strategy>::<rationale>' format" in rejected_capture.stdout
    assert "feature-first::Keep bot-connection, workspace, and publish-log isolated by" in rejected_capture.stdout
    assert "capability" in rejected_capture.stdout


def test_memory_capture_rejects_screen_data_with_extra_segments(tmp_path: Path, monkeypatch) -> None:
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
            "capture",
            "--branch",
            "main",
            "--stage",
            "mvp.design",
            "--screen-data",
            "publish-log::displayed::publish-events::extra",
        ],
    )

    assert result.exit_code == 1, result.stdout
    assert "Capture rejected. Fix the validation errors below." in result.stdout
    assert "screen-data must use '<screen-id>::<displayed|input>::<name>' format" in result.stdout
    assert "field identifier only" in result.stdout


def test_memory_checkpoint_shows_validation_reject_without_allowed_stages(tmp_path: Path, monkeypatch) -> None:
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
            "mvp.architecture",
            "--summary",
            "Ratify incomplete architecture state",
        ],
    )

    assert result.exit_code == 1, result.stdout
    assert "Checkpoint rejected. Fix the validation errors below." in result.stdout
    assert "Allowed stages:" not in result.stdout
    assert "architecture state must include an architecture overview before checkpoint" in result.stdout


def test_memory_checkpoint_invalid_stage_still_shows_allowed_stages(tmp_path: Path, monkeypatch) -> None:
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
            "mvp.fake",
            "--summary",
            "Invalid stage",
        ],
    )

    assert result.exit_code == 1, result.stdout
    assert "Checkpoint rejected. Allowed stages:" in result.stdout
    assert "stage must be one of:" in result.stdout


# ── --from-file tests ──────────────────────────────────────────────────────────


def test_memory_capture_from_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    args_file = tmp_path / "capture-args.json"
    args_file.write_text(
        json.dumps({
            "stage": "mvp.concept",
            "branch": "main",
            "json_output": True,
            "project_name": "FromFileProject",
            "system_overview": "A system built via --from-file.",
            "audiences": ["Developers"],
            "scenarios": ["Deploy from CI"],
            "pain_points": ["Manual setup"],
            "feature_p1": ["CI Pipeline::Automated deploy"],
            "constraints": ["Must run on Linux"],
            "next_actions": ["Proceed to design"],
        }),
        encoding="utf-8",
    )

    result = runner.invoke(cli.app, ["memory", "capture", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True


def test_memory_capture_from_file_missing_stage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    args_file = tmp_path / "capture-args.json"
    args_file.write_text(json.dumps({"summary": "No stage provided"}), encoding="utf-8")

    result = runner.invoke(cli.app, ["memory", "capture", "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert "--stage is required" in result.stdout


def test_memory_capture_from_file_bad_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    args_file = tmp_path / "bad.json"
    args_file.write_text("not json {{{", encoding="utf-8")

    result = runner.invoke(cli.app, ["memory", "capture", "--from-file", str(args_file)])
    assert result.exit_code != 0


def test_memory_capture_from_file_not_found(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli.app, ["memory", "capture", "--from-file", str(tmp_path / "missing.json")])
    assert result.exit_code != 0


def test_memory_checkpoint_from_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    capture_args = tmp_path / "capture.json"
    capture_args.write_text(
        json.dumps({
            "stage": "mvp.concept",
            "branch": "main",
            "project_name": "CheckpointTest",
            "system_overview": "Test system for checkpoint from-file.",
            "audiences": ["QA Engineers"],
            "scenarios": ["Run tests in CI"],
            "pain_points": ["Manual QA is slow"],
            "feature_p1": ["Test::Test feature"],
        }),
        encoding="utf-8",
    )
    capture_result = runner.invoke(cli.app, ["memory", "capture", "--from-file", str(capture_args), "--json-output"])
    assert capture_result.exit_code == 0, capture_result.stdout

    checkpoint_args = tmp_path / "checkpoint.json"
    checkpoint_args.write_text(
        json.dumps({
            "stage": "mvp.concept",
            "branch": "main",
            "summary": "Concept checkpoint via --from-file",
            "evidence": [".madspec/main/concept.md"],
        }),
        encoding="utf-8",
    )
    result = runner.invoke(cli.app, ["memory", "checkpoint", "--from-file", str(checkpoint_args), "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True


def test_memory_checkpoint_from_file_missing_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_path = tmp_path
    (project_path / ".madspec").mkdir()
    (project_path / ".madspec" / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    args_file = tmp_path / "checkpoint.json"
    args_file.write_text(json.dumps({"stage": "mvp.concept"}), encoding="utf-8")

    result = runner.invoke(cli.app, ["memory", "checkpoint", "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert "--summary is required" in result.stdout


def test_memory_register_step_from_file(tmp_path: Path, monkeypatch) -> None:
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
        "# Concept\n\n### Приоритет 1\n- Auth: sign in users\n",
        encoding="utf-8",
    )
    runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    _create_step_artifacts(branch_dir, "step-01-auth")

    args_file = tmp_path / "register.json"
    args_file.write_text(
        json.dumps({
            "stage": "mvp.plan",
            "branch": "main",
            "step_id": "step-01-auth",
            "step_kind": "code",
            "covers": ["Auth"],
        }),
        encoding="utf-8",
    )

    result = runner.invoke(cli.app, ["memory", "register-step", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True


def test_memory_register_step_from_file_missing_required(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    args_file = tmp_path / "register.json"
    args_file.write_text(json.dumps({"stage": "mvp.plan"}), encoding="utf-8")

    result = runner.invoke(cli.app, ["memory", "register-step", "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert "--step-id is required" in result.stdout


def test_memory_implementation_lifecycle_from_file(tmp_path: Path, monkeypatch) -> None:
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
        "# Concept\n\n### Приоритет 1\n- Auth: sign in\n",
        encoding="utf-8",
    )
    runner.invoke(cli.app, ["memory", "init", "--branch", "main"])
    _create_step_artifacts(branch_dir, "step-01-auth")

    runner.invoke(
        cli.app,
        [
            "memory", "register-step",
            "--branch", "main",
            "--stage", "mvp.plan",
            "--step-id", "step-01-auth",
            "--step-kind", "code",
            "--covers", "Auth",
            "--json-output",
        ],
    )

    start_file = tmp_path / "start.json"
    start_file.write_text(
        json.dumps({"stage": "mvp.implement", "branch": "main"}),
        encoding="utf-8",
    )
    start_result = runner.invoke(cli.app, ["memory", "start-step", "--from-file", str(start_file), "--json-output"])
    assert start_result.exit_code == 0, start_result.stdout
    assert json.loads(start_result.stdout)["step_id"] == "step-01-auth"

    checkpoint_file = tmp_path / "checkpoint-step.json"
    checkpoint_file.write_text(
        json.dumps({
            "stage": "mvp.implement",
            "branch": "main",
            "step_id": "step-01-auth",
            "tdd_phase": "red",
            "summary": "Red phase via from-file",
            "red_evidence": ["pytest tests/test_auth.py"],
        }),
        encoding="utf-8",
    )
    cp_result = runner.invoke(cli.app, ["memory", "checkpoint-step", "--from-file", str(checkpoint_file), "--json-output"])
    assert cp_result.exit_code == 0, cp_result.stdout
    cp_payload = json.loads(cp_result.stdout)
    assert cp_payload["tdd_phase"] == "red"

    complete_file = tmp_path / "complete.json"
    complete_file.write_text(
        json.dumps({
            "stage": "mvp.implement",
            "branch": "main",
            "step_id": "step-01-auth",
            "summary": "Auth completed via from-file",
            "green_evidence": ["pytest tests/test_auth.py"],
            "refactor_note": "No refactor needed.",
            "facts": ["Auth uses JWT tokens"],
            "decisions": ["Chose bcrypt for hashing"],
        }),
        encoding="utf-8",
    )
    complete_result = runner.invoke(cli.app, ["memory", "complete-step", "--from-file", str(complete_file), "--json-output"])
    assert complete_result.exit_code == 0, complete_result.stdout
    complete_payload = json.loads(complete_result.stdout)
    assert complete_payload["written"]["facts"] == 1
    assert complete_payload["written"]["decisions"] == 1


def test_memory_complete_step_from_file_missing_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    args_file = tmp_path / "complete.json"
    args_file.write_text(json.dumps({"stage": "mvp.implement"}), encoding="utf-8")

    result = runner.invoke(cli.app, ["memory", "complete-step", "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert "--summary is required" in result.stdout


def test_memory_start_step_from_file_missing_stage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    args_file = tmp_path / "start.json"
    args_file.write_text(json.dumps({"step_id": "step-01"}), encoding="utf-8")

    result = runner.invoke(cli.app, ["memory", "start-step", "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert "--stage is required" in result.stdout


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
