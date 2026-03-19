from __future__ import annotations

from madspec_cli.memory.semantic.capture_inputs import build_capture_inputs
from madspec_cli.memory.semantic.capture_prepare import prepare_capture
from madspec_cli.memory.semantic.capture_stage_bundles import build_parsed_stage_bundle
from madspec_cli.memory.shared.text_lists import normalize_plain_text_list_with_repairs


def test_normalize_plain_text_list_with_repairs_leaves_mixed_payload_unchanged() -> None:
    normalized, warnings = normalize_plain_text_list_with_repairs(
        ["Manual setup", "A", "B"],
        field_name="pain_points",
    )

    assert normalized == ["Manual setup", "A", "B"]
    assert warnings == []


def test_build_capture_inputs_accumulates_trimmed_scalars_and_repair_warnings() -> None:
    inputs = build_capture_inputs(
        stage="mvp.concept",
        status="validated",
        summary="  Capture summary  ",
        project_name="  Repair Project  ",
        audiences=list("Puzzle fans"),
        pain_points=list("Manual setup is slow"),
        feature_p1=[" Core Loop::Play instantly "],
    )

    assert inputs.summary == "Capture summary"
    assert inputs.project_name == "Repair Project"
    assert inputs.audiences == ["Puzzle fans"]
    assert inputs.pain_points == ["Manual setup is slow"]
    assert inputs.feature_p1 == ["Core Loop::Play instantly"]
    assert [warning["field"] for warning in inputs.warnings] == ["audiences", "pain_points"]


def test_build_parsed_stage_bundle_parses_feature_init_inputs() -> None:
    inputs = build_capture_inputs(
        stage="feature.init",
        status="validated",
        feature_p1=["AUTH-1::Auth slice::Implement sign-in flow"],
        existing_modules=["auth::src/auth.py::Authentication helpers"],
        modified_files=["src/auth.py::Add auth flow::login_user"],
        new_files=["src/session.py::Store session state::save_session"],
        dependencies=["internal::session-store::Persist sessions"],
    )

    parsed = build_parsed_stage_bundle(inputs)

    assert parsed.concept_feature_updates == {"p1": [], "p2": [], "p3": []}
    assert parsed.feature_init_feature_updates["p1"][0]["id"] == "AUTH-1"
    assert parsed.feature_existing_modules[0]["name"] == "auth"
    assert parsed.feature_modified_files[0]["path"] == "src/auth.py"
    assert parsed.feature_new_files[0]["path"] == "src/session.py"
    assert parsed.feature_dependencies[0]["name"] == "session-store"


def test_prepare_capture_enriches_feature_init_payload() -> None:
    inputs = build_capture_inputs(
        stage="feature.init",
        status="validated",
        feature_goal="Ship sign-in flow",
        problem="Users cannot log in",
        expected_outcome="Sign-in works end to end",
        feature_p1=["AUTH-1::Auth slice::Implement sign-in flow"],
        existing_modules=["auth::src/auth.py::Authentication helpers"],
        modified_files=["src/auth.py::Add auth flow::login_user"],
        new_files=["src/session.py::Store session state::save_session"],
        dependencies=["internal::session-store::Persist sessions"],
        interface_contracts=["Auth API contract"],
        recommendations=["Reuse auth middleware"],
        risks=["Session migration may fail"],
        tech_notes=["Auth relies on existing token parser"],
        architecture_notes=["Session storage touches persistence layer"],
    )
    parsed = build_parsed_stage_bundle(inputs)

    prepared = prepare_capture(branch_name="main", inputs=inputs, parsed=parsed)

    assert not isinstance(prepared, dict)
    assert "Ship sign-in flow" in prepared.inputs.facts
    assert "Risk: Session migration may fail" in prepared.inputs.facts
    assert "Recommendation: Reuse auth middleware" in prepared.inputs.decisions
    assert "Auth API contract" in prepared.inputs.contracts
    assert any(item.startswith("internal session-store:") for item in prepared.inputs.contracts)
