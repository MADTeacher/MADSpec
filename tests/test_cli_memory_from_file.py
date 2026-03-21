from __future__ import annotations

import json

import pytest

from madspec_cli.memory import get_memory_paths


def test_memory_capture_from_file(make_madspec_project, invoke_cli, write_args_file) -> None:
    make_madspec_project()
    args_file = write_args_file(
        "capture-args.json",
        {
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
        },
    )

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["accepted"] is True


@pytest.mark.parametrize(
    ("file_name", "payload", "expected_written"),
    [
        (
            "capture-aliases.json",
            {
                "stage": "mvp.concept",
                "branch": "main",
                "project_name": "AliasProject",
                "system_overview": "A system built via CLI-style aliases.",
                "audience": ["Developers"],
                "scenario": ["Deploy from CI"],
                "pain": ["Manual setup"],
                "feature_p1": ["CI Pipeline::Automated deploy"],
                "constraint": ["Must run on Linux"],
                "next_action": ["Proceed to design"],
            },
            None,
        ),
        (
            "capture-hyphenated.json",
            {
                "stage": "review",
                "branch": "main",
                "summary": "Review findings from JSON aliases",
                "fact": ["Observed issue in review flow"],
                "pending-action": ["Investigate retry handling"],
            },
            {"facts": 1, "pending_actions": 1},
        ),
    ],
)
def test_memory_capture_from_file_accepts_alias_variants(
    make_madspec_project,
    invoke_cli,
    write_args_file,
    file_name,
    payload,
    expected_written,
) -> None:
    make_madspec_project()
    args_file = write_args_file(file_name, payload)

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed["accepted"] is True
    if expected_written is not None:
        for key, value in expected_written.items():
            assert parsed["written"][key] == value


@pytest.mark.parametrize(
    ("file_name", "field_name", "payload_value", "expected_state_key", "expected_item"),
    [
        (
            "capture-char-split-pain.json",
            "pain_points",
            list("Manual setup is slow"),
            "painPoints",
            "Manual setup is slow",
        ),
        (
            "capture-char-split-audience.json",
            "audiences",
            list("Puzzle fans"),
            "audiences",
            "Puzzle fans",
        ),
    ],
)
def test_memory_capture_from_file_repairs_char_split_fields(
    make_madspec_project,
    invoke_cli,
    write_args_file,
    file_name,
    field_name,
    payload_value,
    expected_state_key,
    expected_item,
) -> None:
    project_path = make_madspec_project()
    args_file = write_args_file(
        file_name,
        {
            "stage": "mvp.concept",
            "branch": "main",
            "project_name": "RepairProject",
            "system_overview": "A system that validates input payloads.",
            "audiences": ["Developers"] if field_name != "audiences" else payload_value,
            "scenarios": ["Capture structured memory from JSON files"],
            "pain_points": ["Manual setup is slow"] if field_name != "pain_points" else payload_value,
            "feature_p1": ["CLI Guardrail::Repair broken plain-text list payloads"],
        },
    )

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    assert payload["warnings"] == [
        {
            "field": field_name,
            "code": "char_split_join",
            "message": "Detected an array of single-character strings and joined it into one text item.",
        }
    ]

    concept_state = json.loads(get_memory_paths(project_path, "main")["concept_state"].read_text(encoding="utf-8"))
    assert concept_state[expected_state_key] == [expected_item]


def test_memory_capture_from_file_regular_text_lists_do_not_warn(
    make_madspec_project,
    invoke_cli,
    write_args_file,
) -> None:
    project_path = make_madspec_project()
    args_file = write_args_file(
        "capture-regular-text-lists.json",
        {
            "stage": "mvp.concept",
            "branch": "main",
            "project_name": "RegularListsProject",
            "system_overview": "A system that validates input payloads.",
            "audiences": ["Developers", "QA Engineers"],
            "scenarios": ["Capture structured memory from JSON files"],
            "pain_points": ["Manual setup is slow"],
            "feature_p1": ["CLI Guardrail::Repair broken plain-text list payloads"],
        },
    )

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    assert payload["warnings"] == []

    concept_state = json.loads(get_memory_paths(project_path, "main")["concept_state"].read_text(encoding="utf-8"))
    assert concept_state["audiences"] == ["Developers", "QA Engineers"]
    assert concept_state["painPoints"] == ["Manual setup is slow"]


def test_memory_capture_from_file_mixed_single_char_payload_is_not_joined(
    make_madspec_project,
    invoke_cli,
    write_args_file,
) -> None:
    project_path = make_madspec_project()
    args_file = write_args_file(
        "capture-mixed-text-lists.json",
        {
            "stage": "mvp.concept",
            "branch": "main",
            "project_name": "MixedListsProject",
            "system_overview": "A system that validates input payloads.",
            "audiences": ["Gamers"],
            "scenarios": ["Open a game in the browser"],
            "pain_points": ["A", "B", "C"],
            "feature_p1": ["Quick Start::Launch a game instantly in the browser"],
        },
    )

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    assert payload["warnings"] == []

    concept_state = json.loads(get_memory_paths(project_path, "main")["concept_state"].read_text(encoding="utf-8"))
    assert concept_state["painPoints"] == ["A", "B", "C"]


def test_memory_capture_from_file_missing_stage(make_madspec_project, invoke_cli, write_args_file) -> None:
    make_madspec_project()
    args_file = write_args_file("capture-missing-stage.json", {"summary": "No stage provided"})

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert "--stage is required" in result.stdout


def test_memory_capture_from_file_bad_json(tmp_path, monkeypatch, invoke_cli, write_args_file) -> None:
    monkeypatch.chdir(tmp_path)
    args_file = write_args_file("bad.json", "not json {{{")

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file)])
    assert result.exit_code != 0


def test_memory_capture_from_file_not_found(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)

    result = invoke_cli(["memory", "capture", "--from-file", str(tmp_path / "missing.json")])
    assert result.exit_code != 0


def test_memory_checkpoint_from_file(make_madspec_project, invoke_cli, write_args_file) -> None:
    make_madspec_project()
    capture_args = write_args_file(
        "capture.json",
        {
            "stage": "mvp.concept",
            "branch": "main",
            "project_name": "CheckpointTest",
            "system_overview": "Test system for checkpoint from-file.",
            "audiences": ["QA Engineers"],
            "scenarios": ["Run tests in CI"],
            "pain_points": ["Manual QA is slow"],
            "feature_p1": ["Test::Test feature"],
        },
    )
    capture_result = invoke_cli(["memory", "capture", "--from-file", str(capture_args), "--json-output"])
    assert capture_result.exit_code == 0, capture_result.stdout

    checkpoint_args = write_args_file(
        "checkpoint.json",
        {
            "stage": "mvp.concept",
            "branch": "main",
            "summary": "Concept checkpoint via --from-file",
            "evidence": [".madspec/main/concept.md"],
        },
    )
    result = invoke_cli(["memory", "checkpoint", "--from-file", str(checkpoint_args), "--json-output"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["accepted"] is True


def test_memory_checkpoint_from_file_accepts_alias_keys(make_madspec_project, invoke_cli, write_args_file) -> None:
    make_madspec_project()
    capture_args = write_args_file(
        "capture.json",
        {
            "stage": "mvp.concept",
            "branch": "main",
            "project_name": "CheckpointAliasTest",
            "system_overview": "Test system for checkpoint alias support.",
            "audiences": ["QA Engineers"],
            "scenarios": ["Run tests in CI"],
            "pain_points": ["Manual QA is slow"],
            "feature_p1": ["Test::Test feature"],
        },
    )
    capture_result = invoke_cli(["memory", "capture", "--from-file", str(capture_args), "--json-output"])
    assert capture_result.exit_code == 0, capture_result.stdout

    checkpoint_args = write_args_file(
        "checkpoint-alias.json",
        {
            "stage": "mvp.concept",
            "branch": "main",
            "summary": "Checkpoint via alias keys",
            "fact": ["Validated concept"],
            "pending_action": ["Start design"],
        },
    )

    result = invoke_cli(["memory", "checkpoint", "--from-file", str(checkpoint_args), "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    assert payload["written"]["decision_log"] == 1
    assert payload["written"]["facts"] == 1


def test_memory_checkpoint_from_file_missing_summary(make_madspec_project, invoke_cli, write_args_file) -> None:
    make_madspec_project()
    args_file = write_args_file("checkpoint-missing-summary.json", {"stage": "mvp.concept"})

    result = invoke_cli(["memory", "checkpoint", "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert "--summary is required" in result.stdout


def test_memory_register_step_from_file(
    make_madspec_project,
    invoke_cli,
    write_args_file,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_short")
    invoke_cli(["memory", "init", "--branch", "main"])
    create_step_artifacts(branch_dir, "step-01-auth")

    args_file = write_args_file(
        "register.json",
        {
            "stage": "mvp.plan",
            "branch": "main",
            "step_id": "step-01-auth",
            "step_kind": "code",
            "covers": ["Auth"],
        },
    )

    result = invoke_cli(["memory", "register-step", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["accepted"] is True


def test_memory_register_step_from_file_accepts_hyphenated_alias_keys(
    make_madspec_project,
    invoke_cli,
    write_args_file,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_short")
    invoke_cli(["memory", "init", "--branch", "main"])
    create_step_artifacts(branch_dir, "step-01-auth")

    args_file = write_args_file(
        "register-hyphen.json",
        {
            "stage": "mvp.plan",
            "branch": "main",
            "step-id": "step-01-auth",
            "step-kind": "code",
            "covers": ["Auth"],
            "related-artifact": ["steps/step-01-auth/tasks.md"],
        },
    )

    result = invoke_cli(["memory", "register-step", "--from-file", str(args_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["accepted"] is True


def test_memory_register_step_from_file_missing_required(tmp_path, monkeypatch, invoke_cli, write_args_file) -> None:
    monkeypatch.chdir(tmp_path)
    args_file = write_args_file("register-missing.json", {"stage": "mvp.plan"})

    result = invoke_cli(["memory", "register-step", "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert "--step-id is required" in result.stdout


def test_memory_implementation_lifecycle_from_file(
    make_madspec_project,
    invoke_cli,
    write_args_file,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_short_sign_in")
    invoke_cli(["memory", "init", "--branch", "main"])
    create_step_artifacts(branch_dir, "step-01-auth")

    invoke_cli(
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
            "code",
            "--covers",
            "Auth",
            "--json-output",
        ]
    )

    start_file = write_args_file("start.json", {"stage": "mvp.implement", "branch": "main"})
    start_result = invoke_cli(["memory", "start-step", "--from-file", str(start_file), "--json-output"])
    assert start_result.exit_code == 0, start_result.stdout
    assert json.loads(start_result.stdout)["step_id"] == "step-01-auth"

    checkpoint_file = write_args_file(
        "checkpoint-step.json",
        {
            "stage": "mvp.implement",
            "branch": "main",
            "step_id": "step-01-auth",
            "tdd_phase": "red",
            "summary": "Red phase via from-file",
            "red_evidence": ["pytest tests/test_auth.py"],
        },
    )
    cp_result = invoke_cli(["memory", "checkpoint-step", "--from-file", str(checkpoint_file), "--json-output"])
    assert cp_result.exit_code == 0, cp_result.stdout
    assert json.loads(cp_result.stdout)["tdd_phase"] == "red"

    complete_file = write_args_file(
        "complete.json",
        {
            "stage": "mvp.implement",
            "branch": "main",
            "step_id": "step-01-auth",
            "summary": "Auth completed via from-file",
            "green_evidence": ["pytest tests/test_auth.py"],
            "refactor_note": "No refactor needed.",
            "facts": ["Auth uses JWT tokens"],
            "decisions": ["Chose bcrypt for hashing"],
        },
    )
    complete_result = invoke_cli(["memory", "complete-step", "--from-file", str(complete_file), "--json-output"])
    assert complete_result.exit_code == 0, complete_result.stdout
    complete_payload = json.loads(complete_result.stdout)
    assert complete_payload["written"]["facts"] == 1
    assert complete_payload["written"]["decisions"] == 1


def test_memory_complete_step_from_file_accepts_alias_keys(
    make_madspec_project,
    invoke_cli,
    write_args_file,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_short_sign_in")
    invoke_cli(["memory", "init", "--branch", "main"])
    create_step_artifacts(branch_dir, "step-01-auth")

    invoke_cli(
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
            "code",
            "--covers",
            "Auth",
            "--json-output",
        ]
    )

    start_file = write_args_file("start.json", {"stage": "mvp.implement", "branch": "main"})
    start_result = invoke_cli(["memory", "start-step", "--from-file", str(start_file), "--json-output"])
    assert start_result.exit_code == 0, start_result.stdout

    complete_file = write_args_file(
        "complete-alias.json",
        {
            "stage": "mvp.implement",
            "branch": "main",
            "step-id": "step-01-auth",
            "summary": "Auth completed via alias keys",
            "red-evidence": ["pytest tests/test_auth.py"],
            "green-evidence": ["pytest tests/test_auth.py"],
            "refactor-note": "No refactor needed.",
            "fact": ["Auth uses JWT tokens"],
            "decision": ["Chose bcrypt for hashing"],
            "contract": ["Password hash stays internal"],
        },
    )

    result = invoke_cli(["memory", "complete-step", "--from-file", str(complete_file), "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["written"]["facts"] == 1
    assert payload["written"]["decisions"] == 1
    assert payload["written"]["contracts"] == 1


def test_memory_from_file_rejects_unknown_fields_with_cli_error(
    tmp_path,
    monkeypatch,
    invoke_cli,
    write_args_file,
) -> None:
    monkeypatch.chdir(tmp_path)
    args_file = write_args_file("capture-unknown.json", {"stage": "mvp.concept", "mystery_field": "???"})

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file)])
    assert result.exit_code != 0
    assert "Unsupported fields in args file: mystery_field" in (result.stdout + result.stderr)
    assert "TypeError" not in result.stdout


@pytest.mark.parametrize(
    ("command", "file_name", "payload", "expected_message"),
    [
        ("complete-step", "complete-missing-summary.json", {"stage": "mvp.implement"}, "--summary is required"),
        ("start-step", "start-missing-stage.json", {"step_id": "step-01"}, "--stage is required"),
    ],
)
def test_memory_from_file_missing_required_fields(
    tmp_path,
    monkeypatch,
    invoke_cli,
    write_args_file,
    command,
    file_name,
    payload,
    expected_message,
) -> None:
    monkeypatch.chdir(tmp_path)
    args_file = write_args_file(file_name, payload)

    result = invoke_cli(["memory", command, "--from-file", str(args_file)])
    assert result.exit_code == 1
    assert expected_message in result.stdout


def test_memory_capture_from_tmp_file_deletes_args_on_success(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    tmp_dir = project_path / ".madspec" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    args_file = tmp_dir / "capture-args.json"
    args_file.write_text(
        json.dumps(
            {
                "stage": "mvp.concept",
                "branch": "main",
                "project_name": "TmpCleanupProject",
                "system_overview": "A system built via .madspec/.tmp.",
                "audiences": ["Developers"],
                "scenarios": ["Run capture from temp input"],
                "pain_points": ["Temp files accumulate"],
                "feature_p1": ["Cleanup::Delete temp file on success"],
            }
        ),
        encoding="utf-8",
    )

    result = invoke_cli(["memory", "capture", "--from-file", ".madspec/.tmp/capture-args.json", "--json-output"])

    assert result.exit_code == 0, result.stdout
    assert not args_file.exists()


@pytest.mark.parametrize(
    ("command", "file_name", "payload", "setup"),
    [
        ("capture", "capture-fail.json", {"summary": "Missing stage"}, None),
        ("checkpoint", "checkpoint-fail.json", {"stage": "mvp.concept"}, None),
        ("register-step", "register-fail.json", {"stage": "mvp.plan"}, "planning"),
        ("start-step", "start-fail.json", {"step_id": "step-01"}, None),
        ("checkpoint-step", "checkpoint-step-fail.json", {"stage": "mvp.implement"}, None),
        ("complete-step", "complete-step-fail.json", {"stage": "mvp.implement"}, None),
    ],
)
def test_memory_tmp_args_file_is_kept_on_failure(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
    command,
    file_name,
    payload,
    setup,
) -> None:
    project_path = make_madspec_project()
    if setup == "planning":
        branch_dir = project_path / ".madspec" / "main"
        branch_dir.mkdir(parents=True, exist_ok=True)
        write_concept_markdown(branch_dir, variant="auth_short")
        init_result = invoke_cli(["memory", "init", "--branch", "main"])
        assert init_result.exit_code == 0, init_result.stdout
        create_step_artifacts(branch_dir, "step-01-auth")

    tmp_dir = project_path / ".madspec" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    args_file = tmp_dir / file_name
    args_file.write_text(json.dumps(payload), encoding="utf-8")

    result = invoke_cli(["memory", command, "--from-file", f".madspec/.tmp/{file_name}"])

    assert result.exit_code == 1
    assert args_file.exists()


def test_memory_capture_from_external_file_keeps_args_on_success(
    make_madspec_project,
    invoke_cli,
    write_args_file,
) -> None:
    make_madspec_project()
    args_file = write_args_file(
        "external-capture.json",
        {
            "stage": "mvp.concept",
            "branch": "main",
            "project_name": "ExternalFileProject",
            "system_overview": "A system built from an external args file.",
            "audiences": ["Developers"],
            "scenarios": ["Use external temp path"],
            "pain_points": ["Unexpected deletions"],
            "feature_p1": ["Safety::Do not delete external input"],
        },
    )

    result = invoke_cli(["memory", "capture", "--from-file", str(args_file), "--json-output"])

    assert result.exit_code == 0, result.stdout
    assert args_file.exists()
