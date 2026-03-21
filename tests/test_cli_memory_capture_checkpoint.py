from __future__ import annotations

import json

from madspec_cli.memory import get_memory_paths


def test_memory_checkpoint_updates_memory_and_retrieve_context(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    capture_result = invoke_cli(
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
        ]
    )
    assert capture_result.exit_code == 0, capture_result.stdout

    result = invoke_cli(
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
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True

    active_session_path = get_memory_paths(project_path, "main")["active_session"]
    active_session = json.loads(active_session_path.read_text(encoding="utf-8"))
    assert active_session["stage"] == "mvp.concept"
    assert active_session["active_goal"] == "Concept validated for MVP scheduling assistant"
    assert active_session["open_questions"] == ["Should team bookings be part of MVP?"]
    assert active_session["pending_actions"] == ["Proceed to mvp.design"]

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.concept", "--json-output"]
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
    assert (
        retrieve_payload["concept_status"]["last_checkpoint_summary"]
        == "Concept validated for MVP scheduling assistant"
    )
    assert (
        retrieve_payload["semantic"]["contracts"][0]["summary"]
        == "Reminder settings must stay editable per booking"
    )
    assert retrieve_payload["episodes"] == []
    assert retrieve_payload["decision_log"] == []

    retrieve_full_result = invoke_cli(
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
        ]
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert retrieve_full_payload["artifact_state"]["concept"]["projectName"] == "MVP scheduling assistant"
    assert (
        retrieve_full_payload["artifact_state"]["concept"]["systemOverview"]
        == "System helps freelancers manage bookings and reminders from one interface."
    )
    assert (
        retrieve_full_payload["artifact_state"]["concept"]["checkpointSummary"]
        == "Concept validated for MVP scheduling assistant"
    )
    assert retrieve_full_payload["artifact_state"]["concept"]["features"]["p1"] == [
        {"name": "Booking workflow", "description": "Create bookings and send reminders"}
    ]
    assert retrieve_full_payload["decision_log"] != []

    project_context = (project_path / ".madspec" / "main" / "project-context.md").read_text(encoding="utf-8")
    assert "Current stage: `mvp.concept`" in project_context
    assert "Active goal: `Concept validated for MVP scheduling assistant`" in project_context
    assert "Concept checkpoint summary: `Concept validated for MVP scheduling assistant`" in project_context
    assert "## Current Gate Status" in project_context
    assert "## Review Gates" in project_context
    assert "## Security Gates" in project_context


def test_memory_capture_supports_incremental_non_iterative_stages(make_madspec_project, invoke_cli) -> None:
    make_madspec_project()

    capture_result = invoke_cli(
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
        ]
    )
    assert capture_result.exit_code == 0, capture_result.stdout
    capture_payload = json.loads(capture_result.stdout)
    assert capture_payload["written"]["facts"] == 6
    assert capture_payload["written"]["decisions"] == 1

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.concept", "--json-output"]
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

    checkpoint_result = invoke_cli(
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
        ]
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout
    checkpoint_payload = json.loads(checkpoint_result.stdout)
    assert checkpoint_payload["used_existing_stage_memory"] is True


def test_memory_capture_supports_design_stage_state_and_retrieve(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    branch_name = "main"

    ui_dir = project_path / ".madspec" / branch_name / "ui-prototype"
    ui_dir.mkdir(parents=True)
    for name in ("index.html", "schedule-board.html", "profile-studio.html", "export-hub.html"):
        (ui_dir / name).write_text(f"<html><body>{name}</body></html>\n", encoding="utf-8")

    concept_capture = invoke_cli(
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
        ]
    )
    assert concept_capture.exit_code == 0, concept_capture.stdout

    design_capture = invoke_cli(
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
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/index.html::Shows upcoming bookings and reminder actions",
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
        ]
    )
    assert design_capture.exit_code == 0, design_capture.stdout

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", branch_name, "--stage", "mvp.design", "--json-output"]
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
    assert retrieve_payload["design_status"]["uncovered_features"] == {"p1": [], "p2": [], "p3": []}
    assert retrieve_payload["design_status"]["missing_prototype_files"] == []
    assert retrieve_payload["decision_log"] == []
    assert retrieve_payload["artifact_state"]["design"] is None

    checkpoint_result = invoke_cli(
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
        ]
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    retrieve_full_result = invoke_cli(
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
        ]
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert (
        retrieve_full_payload["artifact_state"]["design"]["checkpointSummary"]
        == "Design ratified for prototype review"
    )
    assert retrieve_full_payload["artifact_state"]["design"]["revision"] == 1
    assert retrieve_full_payload["decision_log"] != []
    ui_design = (project_path / ".madspec" / branch_name / "ui-design.md").read_text(encoding="utf-8")
    assert "## Review Journeys" in ui_design
    assert "Storyboard path" in ui_design
    assert "Покрытие функций" not in ui_design


def test_memory_retrieve_returns_tech_status_and_full_artifact(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    capture_result = invoke_cli(
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
        ]
    )
    assert capture_result.exit_code == 0, capture_result.stdout

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.tech", "--limit", "1", "--json-output"]
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

    checkpoint_result = invoke_cli(
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
        ]
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    retrieve_full_result = invoke_cli(
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
        ]
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert retrieve_full_payload["artifact_state"]["tech"]["projectType"] == "Web application"
    assert (
        retrieve_full_payload["artifact_state"]["tech"]["checkpointSummary"]
        == "Tech stack ratified for MVP architecture"
    )
    assert retrieve_full_payload["artifact_state"]["tech"]["revision"] == 1
    assert retrieve_full_payload["decision_log"] != []

    tech_stack = (project_path / ".madspec" / "main" / "tech-stack.md").read_text(encoding="utf-8")
    assert "A Python-first stack optimized for rapid MVP delivery and simple deployment." in tech_stack
    assert "FastAPI" in tech_stack


def test_memory_retrieve_returns_deploy_status_and_full_artifact(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    capture_result = invoke_cli(
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "deploy",
            "--summary",
            "Зафиксировали схему развертывания",
            "--deploy-overview",
            "Контейнерное развертывание с отдельными окружениями stage и prod.",
            "--deploy-goal",
            "Воспроизводимая выкладка",
            "--deploy-goal",
            "Контролируемый откат",
            "--environment",
            "stage::Предрелизная проверка::Проверка миграций и smoke-тестов",
            "--environment",
            "prod::Боевой контур::Обслуживание внешних пользователей",
            "--deployment-unit",
            "api::service::Docker::Обслуживает HTTP API",
            "--deployment-unit",
            "worker::worker::Docker::Выполняет фоновые задачи",
            "--config-note",
            "Конфигурация хранится в переменных окружения",
            "--secret-note",
            "Секреты берутся из внешнего хранилища",
            "--cicd-trigger",
            "Публикация тега релиза",
            "--cicd-step",
            "Сборка образа",
            "--cicd-step",
            "Запуск миграций",
            "--release-artifact",
            "Docker image",
            "--migration-note",
            "Миграции выполняются до переключения трафика",
            "--backup-note",
            "Ежедневный снимок базы данных",
            "--recovery-check",
            "Раз в месяц проверять восстановление на резервном стенде",
            "--observability-note",
            "Логи и метрики собираются централизованно",
            "--security-control",
            "Доступ к prod только через выделенные роли",
            "--release-strategy",
            "Постепенное переключение трафика",
            "--rollback-strategy",
            "Возврат на предыдущий образ и откат миграций при необходимости",
            "--next-action",
            "Уточнить процедуру аварийного восстановления",
            "--json-output",
        ]
    )
    assert capture_result.exit_code == 0, capture_result.stdout

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", "main", "--stage", "deploy", "--json-output"]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["deploy_status"]["is_complete"] is True
    assert retrieve_payload["deploy_status"]["missing_required_fields"] == []
    assert retrieve_payload["deploy_status"]["counts"] == {
        "goals": 2,
        "environments": 2,
        "deployment_units": 2,
        "config_notes": 1,
        "secret_notes": 1,
        "cicd_triggers": 1,
        "cicd_steps": 2,
        "release_artifacts": 1,
        "migration_notes": 1,
        "backup_notes": 1,
        "recovery_checks": 1,
        "observability_notes": 1,
        "security_controls": 1,
        "constraints": 0,
        "next_actions": 1,
    }
    assert retrieve_payload["artifact_state"]["deploy"] is None

    checkpoint_result = invoke_cli(
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "deploy",
            "--summary",
            "План развертывания подтвержден для релизной подготовки",
            "--evidence",
            ".madspec/main/deployment.md",
            "--json-output",
        ]
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    retrieve_full_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "deploy",
            "--full-artifact",
            "--include-history",
            "--json-output",
        ]
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert (
        retrieve_full_payload["artifact_state"]["deploy"]["checkpointSummary"]
        == "План развертывания подтвержден для релизной подготовки"
    )
    assert retrieve_full_payload["artifact_state"]["deploy"]["revision"] == 1
    assert retrieve_full_payload["decision_log"] != []

    deployment_doc = (project_path / ".madspec" / "main" / "deployment.md").read_text(encoding="utf-8")
    assert "План развертывания" in deployment_doc
    assert "Постепенное переключение трафика" in deployment_doc


def test_memory_capture_supports_architecture_stage_state_and_retrieve(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    branch_name = "main"

    ui_dir = project_path / ".madspec" / branch_name / "ui-prototype"
    ui_dir.mkdir(parents=True)
    for name in ("index.html", "schedule-board.html", "profile-studio.html", "export-hub.html"):
        (ui_dir / name).write_text(f"<html><body>{name}</body></html>\n", encoding="utf-8")

    concept_capture = invoke_cli(
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
        ]
    )
    assert concept_capture.exit_code == 0, concept_capture.stdout

    design_capture = invoke_cli(
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
            "schedule-board::Schedule board::operations::.madspec/main/ui-prototype/index.html::Shows upcoming bookings and reminder actions",
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
        ]
    )
    assert design_capture.exit_code == 0, design_capture.stdout

    architecture_capture = invoke_cli(
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
        ]
    )
    assert architecture_capture.exit_code == 0, architecture_capture.stdout

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", branch_name, "--stage", "mvp.architecture", "--json-output"]
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

    checkpoint_result = invoke_cli(
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
        ]
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    retrieve_full_result = invoke_cli(
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
        ]
    )
    assert retrieve_full_result.exit_code == 0, retrieve_full_result.stdout
    retrieve_full_payload = json.loads(retrieve_full_result.stdout)
    assert (
        retrieve_full_payload["artifact_state"]["architecture"]["checkpointSummary"]
        == "Architecture ratified for implementation planning"
    )
    assert retrieve_full_payload["artifact_state"]["architecture"]["revision"] == 1
    assert retrieve_full_payload["decision_log"] != []

    architecture_doc = (project_path / ".madspec" / "main" / "architecture.md").read_text(encoding="utf-8")
    data_model_doc = (project_path / ".madspec" / "main" / "data-model.md").read_text(encoding="utf-8")
    openapi_doc = (
        project_path / ".madspec" / "main" / "contracts" / "openapi.yaml"
    ).read_text(encoding="utf-8")
    assert "A modular web architecture centered on scheduling workflows" in architecture_doc
    assert "Booking" in data_model_doc
    assert "update-booking-reminder" in openapi_doc


def test_memory_capture_and_checkpoint_support_review_and_security(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    review_capture = invoke_cli(
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
        ]
    )
    assert review_capture.exit_code == 0, review_capture.stdout

    security_capture = invoke_cli(
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
        ]
    )
    assert security_capture.exit_code == 0, security_capture.stdout

    review_checkpoint = invoke_cli(
        ["memory", "checkpoint", "--branch", "main", "--stage", "review", "--summary", "Review ratified", "--json-output"]
    )
    assert review_checkpoint.exit_code == 0, review_checkpoint.stdout

    security_checkpoint = invoke_cli(
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
        ]
    )
    assert security_checkpoint.exit_code == 0, security_checkpoint.stdout

    review_view = (project_path / ".madspec" / "main" / "review.md").read_text(encoding="utf-8")
    security_view = (project_path / ".madspec" / "main" / "security-audit.md").read_text(
        encoding="utf-8"
    )
    assert "Refactor auth service boundaries before scaling" in review_view
    assert "No rate limiting on login endpoint" in security_view
    assert "## Gate Summary" in review_view
    assert "## Gate Summary" in security_view


def test_memory_checkpoint_rejects_incomplete_tech_state(make_madspec_project, invoke_cli) -> None:
    make_madspec_project()

    capture_result = invoke_cli(
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
        ]
    )
    assert capture_result.exit_code == 0, capture_result.stdout

    checkpoint_result = invoke_cli(
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
        ]
    )
    assert checkpoint_result.exit_code == 1, checkpoint_result.stdout
    payload = json.loads(checkpoint_result.stdout)
    assert payload["accepted"] is False
    assert "tech state must include a stack overview before checkpoint" in payload["errors"]


def test_memory_checkpoint_rejects_invalid_stage_and_empty_summary(make_madspec_project, invoke_cli) -> None:
    make_madspec_project()

    invalid_stage = invoke_cli(
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
        ]
    )
    assert invalid_stage.exit_code == 1, invalid_stage.stdout

    empty_summary = invoke_cli(
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
        ]
    )
    assert empty_summary.exit_code == 1, empty_summary.stdout


def test_memory_capture_architecture_accepts_response_alias_and_cleans_reject_message(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    branch_name = "main"

    init_result = invoke_cli(["memory", "init", "--branch", branch_name])
    assert init_result.exit_code == 0, init_result.stdout

    ui_dir = project_path / ".madspec" / branch_name / "ui-prototype"
    ui_dir.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "workspace-main.html", "publish-log.html"):
        (ui_dir / name).write_text(f"<html><body>{name}</body></html>\n", encoding="utf-8")

    concept_capture = invoke_cli(
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
        ]
    )
    assert concept_capture.exit_code == 0, concept_capture.stdout

    design_capture = invoke_cli(
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
        ]
    )
    assert design_capture.exit_code == 0, design_capture.stdout

    architecture_capture = invoke_cli(
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
        ]
    )
    assert architecture_capture.exit_code == 0, architecture_capture.stdout

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", branch_name, "--stage", "mvp.architecture", "--json-output"]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["architecture_status"]["missing_required_fields"] == []
    assert retrieve_payload["architecture_status"]["reference_errors"] == []
    assert retrieve_payload["architecture_status"]["is_complete"] is True

    rejected_capture = invoke_cli(
        [
            "memory",
            "capture",
            "--branch",
            branch_name,
            "--stage",
            "mvp.architecture",
            "--project-structure",
            "backend-first mono-repo without separator",
        ]
    )
    assert rejected_capture.exit_code == 1, rejected_capture.stdout
    assert "Capture rejected. Fix the validation errors below." in rejected_capture.stdout
    assert "Allowed stages:" not in rejected_capture.stdout
    assert "project-structure must use '<strategy>::<rationale>' format" in rejected_capture.stdout
    assert "feature-first::Keep bot-connection, workspace, and publish-log isolated by" in rejected_capture.stdout
    assert "capability" in rejected_capture.stdout


def test_memory_capture_rejects_screen_data_with_extra_segments(make_madspec_project, invoke_cli) -> None:
    make_madspec_project()

    result = invoke_cli(
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "mvp.design",
            "--screen-data",
            "publish-log::displayed::publish-events::extra",
        ]
    )

    assert result.exit_code == 1, result.stdout
    assert "Capture rejected. Fix the validation errors below." in result.stdout
    assert "screen-data must use '<screen-id>::<displayed|input>::<name>' format" in result.stdout
    assert "field identifier only" in result.stdout


def test_memory_checkpoint_shows_validation_reject_without_allowed_stages(
    make_madspec_project,
    invoke_cli,
) -> None:
    make_madspec_project()

    result = invoke_cli(
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "mvp.architecture",
            "--summary",
            "Ratify incomplete architecture state",
        ]
    )

    assert result.exit_code == 1, result.stdout
    assert "Checkpoint rejected. Fix the validation errors below." in result.stdout
    assert "Allowed stages:" not in result.stdout
    assert "architecture state must include an architecture overview before checkpoint" in result.stdout


def test_memory_checkpoint_invalid_stage_still_shows_allowed_stages(
    make_madspec_project,
    invoke_cli,
) -> None:
    make_madspec_project()

    result = invoke_cli(
        [
            "memory",
            "checkpoint",
            "--branch",
            "main",
            "--stage",
            "mvp.fake",
            "--summary",
            "Invalid stage",
        ]
    )

    assert result.exit_code == 1, result.stdout
    assert "Checkpoint rejected. Allowed stages:" in result.stdout
    assert "stage must be one of:" in result.stdout
