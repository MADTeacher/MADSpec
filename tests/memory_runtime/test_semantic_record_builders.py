from __future__ import annotations

from madspec_cli.memory import capture_stage_memory, retrieve_memory_context
from madspec_cli.memory.domain.conflicts import semantic_fingerprint
from madspec_cli.memory.semantic.capture_inputs import build_capture_inputs
from madspec_cli.memory.semantic.capture_persistence import _capture_semantic_fingerprints
from madspec_cli.memory.semantic.capture_prepare import prepare_capture
from madspec_cli.memory.semantic.capture_stage_bundles import build_parsed_stage_bundle
from madspec_cli.memory.semantic.contract_records import build_contract_records
from madspec_cli.memory.semantic.decision_records import build_decision_records
from madspec_cli.memory.semantic.fact_records import build_fact_records
from madspec_cli.memory.semantic.note_records import build_note_records
from madspec_cli.memory.semantic.record_context import RecordBuildContext
from tests.memory_runtime.support import bootstrap_memory_project


def test_note_records_materialize_stage_note_payload() -> None:
    context, _ = _build_context(
        "mvp.plan",
        summary="Lock implementation sequence",
        questions=["Should exports block release?"],
        pending_actions=["Checkpoint plan"],
    )

    records = build_note_records(context)

    assert len(records) == 1
    assert records[0]["summary"] == "Lock implementation sequence"
    assert records[0]["record_type"] == "stage_note"
    assert records[0]["metadata"] == {
        "questions": ["Should exports block release?"],
        "pendingActions": ["Checkpoint plan"],
    }


def test_fact_records_preserve_stage_specific_slots() -> None:
    concept_context, _ = _build_context(
        "mvp.concept",
        project_name="Auth Demo",
        system_overview="Authentication workspace for sign-in and sessions.",
        audiences=["Freelancers"],
        scenarios=["Sign in quickly"],
        pain_points=["Manual session recovery"],
        assumptions=["Email remains primary identifier"],
    )
    design_context, _ = _build_context(
        "mvp.design",
        design_overview="A workspace-first shell for authentication tasks.",
        platforms=["Web"],
        zones=["workspace::Workspace::Primary work area"],
        screens=["home::Home::workspace::.madspec/main/ui-prototype/index.html::Primary screen"],
        flows=["sign-in::Sign in::Authenticate the current user"],
        flow_steps=["sign-in::home::Submit credentials::Session becomes active"],
        screen_data=["home::displayed::session-state"],
    )
    tech_context, _ = _build_context(
        "mvp.tech",
        project_type="cli",
        stack_overview="Python CLI with JSON state",
        requirements=["Support local sessions"],
        preferences=["Prefer stdlib where possible"],
    )
    architecture_context, _ = _build_context(
        "mvp.architecture",
        architecture_overview="Layered service around auth and sessions.",
        project_structure="feature-first::Keep auth and session code isolated",
        directories=["src/auth::Authentication domain and services"],
        entities=["Session::Represents an authenticated session"],
        entity_fields=["Session::user_id::string::required::Authenticated user id"],
        integrations=["Email::external::Deliver one-time codes::auth-service"],
        code_principles=["Keep adapters thin and orchestration explicit."],
        security_notes=["Protect session mutation endpoints."],
        performance_notes=["Cache session lookups during a single command run."],
    )
    plan_context, _ = _build_context(
        "mvp.plan",
        plan_overview="Implement authentication before profile features.",
    )

    concept_records = build_fact_records(concept_context)
    design_records = build_fact_records(design_context)
    tech_records = build_fact_records(tech_context)
    architecture_records = build_fact_records(architecture_context)
    plan_records = build_fact_records(plan_context)

    assert _has_summary(concept_records, "Project name: Auth Demo")
    assert _has_slot(concept_records, "systemOverview")
    assert _has_slot(concept_records, "audience")
    assert _has_summary(design_records, "Design overview: A workspace-first shell for authentication tasks.")
    assert _has_slot(design_records, "screen")
    assert _has_slot(design_records, "flowStep")
    assert _has_summary(tech_records, "Project type: cli")
    assert _has_slot(tech_records, "preference")
    assert _has_summary(architecture_records, "Architecture overview: Layered service around auth and sessions.")
    assert _has_slot(architecture_records, "projectStructure")
    assert _has_slot(architecture_records, "entityField")
    assert _has_slot(architecture_records, "securityNote")
    assert _has_summary(plan_records, "Plan overview: Implement authentication before profile features.")


def test_decision_records_preserve_stage_specific_slots() -> None:
    concept_context, _ = _build_context(
        "mvp.concept",
        feature_p1=["Authentication::Implement sign-in flow"],
    )
    design_context, _ = _build_context(
        "mvp.design",
        screen_features=["home::p1::Authentication"],
        navigation=["home::settings::Open settings"],
        flow_alternatives=["sign-in::Fallback to email code entry"],
    )
    tech_context, _ = _build_context(
        "mvp.tech",
        stack_components=["runtime::python::3.12::Use Python for CLI workflows"],
        libraries=["runtime::typer::0.12::Command-line interface"],
        code_organization="single-repo::src-layout::feature-modules::Keep auth code grouped by feature",
        alternatives=["storage::sqlite::Too heavy for initial workflow state"],
    )
    architecture_context, _ = _build_context(
        "mvp.architecture",
        entity_relationships=["Session::User::belongs-to::Each session belongs to a single user"],
        entity_states=["Session::active::Current session can be used for API calls"],
        endpoints=["sign-in::POST::/sessions::Create a new session"],
        endpoint_screens=["sign-in::home"],
        endpoint_fields=["sign-in::request::email::string::required::User email address"],
        architecture_patterns=["Repository::Hide persistence details behind services"],
    )
    plan_context, _ = _build_context(
        "mvp.plan",
        planning_principles=["Implement sign-in before dependent profile work."],
    )

    concept_records = build_decision_records(concept_context)
    design_records = build_decision_records(design_context)
    tech_records = build_decision_records(tech_context)
    architecture_records = build_decision_records(architecture_context)
    plan_records = build_decision_records(plan_context)

    assert _has_summary(concept_records, "P1 feature: Authentication - Implement sign-in flow")
    assert _has_slot(design_records, "screenFeature")
    assert _has_slot(design_records, "navigation")
    assert _has_slot(design_records, "flowAlternative")
    assert _has_summary(tech_records, "Stack component runtime: python 3.12 - Use Python for CLI workflows")
    assert _has_slot(tech_records, "codeOrganization")
    assert _has_summary(tech_records, "Rejected alternative for storage: sqlite - Too heavy for initial workflow state")
    assert _has_slot(architecture_records, "entityRelationship")
    assert _has_slot(architecture_records, "endpoint")
    assert _has_slot(architecture_records, "pattern")
    assert _has_slot(plan_records, "planningPrinciple")


def test_contract_records_preserve_stage_specific_slots() -> None:
    concept_context, _ = _build_context(
        "mvp.concept",
        constraints=["Do not require IDE-specific tooling"],
    )
    design_context, _ = _build_context(
        "mvp.design",
        contracts=["Primary flow must work on desktop width"],
        platform_constraints=["Web only for MVP"],
    )
    tech_context, _ = _build_context(
        "mvp.tech",
        contracts=["Use UTF-8 JSON for persisted state"],
        tech_constraints=["Avoid mandatory external services during local development"],
    )
    architecture_context, _ = _build_context(
        "mvp.architecture",
        endpoint_errors=["sign-in::401::invalid_credentials::Return an auth error for invalid credentials"],
    )

    concept_records = build_contract_records(concept_context)
    design_records = build_contract_records(design_context)
    tech_records = build_contract_records(tech_context)
    architecture_records = build_contract_records(architecture_context)

    assert _has_slot(concept_records, "constraint")
    assert _has_summary(design_records, "Primary flow must work on desktop width")
    assert _has_slot(design_records, "platformConstraint")
    assert _has_slot(tech_records, "techConstraint")
    assert _has_slot(architecture_records, "endpointError")


def test_capture_semantic_fingerprints_match_builder_outputs() -> None:
    context, prepared = _build_context(
        "mvp.architecture",
        architecture_overview="Layered service around auth and sessions.",
        directories=["src/auth::Authentication domain and services"],
        entities=["Session::Represents an authenticated session"],
        endpoints=["sign-in::POST::/sessions::Create a new session"],
        endpoint_errors=["sign-in::401::invalid_credentials::Return an auth error for invalid credentials"],
        architecture_patterns=["Repository::Hide persistence details behind services"],
    )

    built_records = (
        build_fact_records(context)
        + build_decision_records(context)
        + build_contract_records(context)
    )

    assert _capture_semantic_fingerprints("main", prepared) == {
        semantic_fingerprint(record) for record in built_records
    }


def test_capture_stage_memory_preserves_semantic_payload_for_feature_and_deploy(tmp_path) -> None:
    (tmp_path / "feature").mkdir()
    feature_project = bootstrap_memory_project(tmp_path / "feature")
    feature_capture = capture_stage_memory(
        feature_project.project_path,
        "main",
        "feature.init",
        feature_goal="Ship sign-in flow",
        problem="Users cannot authenticate",
        expected_outcome="Session works end to end",
        project_type="cli",
        framework="Typer",
        feature_p1=["AUTH-1::Auth slice::Implement sign-in flow"],
        existing_modules=["auth::src/auth.py::Authentication helpers"],
        modified_files=["src/auth.py::Add auth flow::login_user"],
        new_files=["src/session.py::Store session state::save_session"],
        interface_contracts=["Auth API contract"],
        dependencies=["internal::session-store::Persist sessions"],
        recommendations=["Reuse auth middleware"],
        risks=["Session migration may fail"],
        tech_notes=["Auth relies on token parser"],
        architecture_notes=["Session storage touches persistence layer"],
    )
    feature_retrieved = retrieve_memory_context(
        feature_project.project_path,
        "main",
        "feature.init",
        full_artifact=True,
    )

    (tmp_path / "deploy").mkdir()
    deploy_project = bootstrap_memory_project(tmp_path / "deploy")
    deploy_capture = capture_stage_memory(
        deploy_project.project_path,
        "main",
        "deploy",
        deploy_overview="Containerized deployment with separate stage and prod environments.",
        deploy_goals=["Ship auth updates safely"],
        environments=["stage::Pre-production verification::Mirror production config"],
        deployment_units=["api::service::docker::Runs authentication API"],
        config_notes=["Load secrets from environment variables"],
        secret_notes=["Rotate auth secrets before release"],
        cicd_triggers=["Push to main"],
        cicd_steps=["Run test suite before deploy"],
        release_artifacts=["Docker image"],
        migration_notes=["No database migration required"],
        backup_notes=["Keep previous image available"],
        recovery_checks=["Verify health endpoint after rollback"],
        observability_notes=["Emit auth failure metrics"],
        security_controls=["Restrict deployment credentials"],
        release_strategy="Blue/green rollout",
        rollback_strategy="Revert to previous image tag",
    )
    deploy_retrieved = retrieve_memory_context(
        deploy_project.project_path,
        "main",
        "deploy",
        full_artifact=True,
    )

    assert feature_capture["accepted"] is True
    assert feature_capture["written"] == {
        "notes": 0,
        "facts": 7,
        "decisions": 4,
        "contracts": 2,
        "questions": 0,
        "pending_actions": 0,
    }
    assert feature_retrieved["artifact_state"]["feature_init"]["featureGoal"] == "Ship sign-in flow"
    assert feature_retrieved["feature_init_status"]["functions_by_priority"]["p1"] == ["AUTH-1"]

    assert deploy_capture["accepted"] is True
    assert deploy_capture["written"] == {
        "notes": 0,
        "facts": 10,
        "decisions": 6,
        "contracts": 0,
        "questions": 0,
        "pending_actions": 0,
    }
    assert deploy_retrieved["artifact_state"]["deploy"]["deployOverview"] == (
        "Containerized deployment with separate stage and prod environments."
    )
    assert deploy_retrieved["artifact_state"]["deploy"]["releaseStrategy"] == "Blue/green rollout"


def _build_context(stage: str, **kwargs):
    inputs = build_capture_inputs(stage=stage, status="validated", **kwargs)
    parsed = build_parsed_stage_bundle(inputs)
    prepared = prepare_capture(branch_name="main", inputs=inputs, parsed=parsed)

    assert not isinstance(prepared, dict)

    return (
        RecordBuildContext(
            branch_name="main",
            ts="2026-03-29T12:00:00Z",
            inputs=prepared.inputs,
            parsed=prepared.parsed,
        ),
        prepared,
    )


def _has_summary(records: list[dict[str, object]], summary: str) -> bool:
    return any(record["summary"] == summary for record in records)


def _has_slot(records: list[dict[str, object]], slot: str) -> bool:
    return any(record.get("metadata", {}).get("slot") == slot for record in records)
