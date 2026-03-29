from __future__ import annotations

from madspec_cli.memory.semantic.capture import capture_stage_memory
from madspec_cli.memory.semantic.capture_payloads import (
    ConceptCapturePayload,
    DesignCapturePayload,
    build_stage_capture_payload,
)
from tests.memory_runtime.support import bootstrap_memory_project


def test_capture_stage_memory_accepts_stage_payload_object(tmp_path) -> None:
    memory_project = bootstrap_memory_project(tmp_path)

    payload = ConceptCapturePayload(
        project_name="Auth Demo",
        system_overview="Authentication and session management workspace.",
        audiences=["Freelancers"],
        scenarios=["Sign in and stay signed in"],
        pain_points=["Manual session recovery"],
        feature_p1=["Authentication::Sign in users"],
    )
    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.concept",
        payload=payload,
    )

    assert captured["accepted"] is True
    assert captured["stage"] == "mvp.concept"


def test_capture_stage_memory_reports_stage_specific_payload_mismatch(tmp_path) -> None:
    memory_project = bootstrap_memory_project(tmp_path)

    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "review",
        payload=DesignCapturePayload(design_overview="Workspace-first UI"),
    )

    assert captured["accepted"] is False
    assert captured["errors"] == [
        "design-specific capture options are only supported for stage mvp.design"
    ]


def test_build_stage_capture_payload_keeps_legacy_capture_path_compatible(tmp_path) -> None:
    memory_project = bootstrap_memory_project(tmp_path)

    payload = build_stage_capture_payload(
        "mvp.design",
        design_overview="Workspace-first UI",
        platforms=["Web"],
        zones=["workspace::Workspace::Main work area"],
        screens=["home::Home::workspace::.madspec/main/ui-prototype/index.html::Primary screen"],
    )
    captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        payload=payload,
        status="validated",
    )
    legacy_captured = capture_stage_memory(
        memory_project.project_path,
        "main",
        "mvp.design",
        design_overview="Workspace-first UI",
        platforms=["Web"],
        zones=["workspace::Workspace::Main work area"],
        screens=["home::Home::workspace::.madspec/main/ui-prototype/index.html::Primary screen"],
        status="validated",
    )

    assert captured["accepted"] is True
    assert legacy_captured["accepted"] is True
