from __future__ import annotations

import json

from madspec_cli.memory.domain.conflicts import PROJECT_MEMORY_BRANCH
from madspec_cli.memory.shared.records import make_record
from madspec_cli.memory.shared.storage import append_jsonl, get_memory_paths, write_json
from madspec_cli.memory.shared.system_store.canonical_state import load_canonical_branch_state
from madspec_cli.memory.shared.system_store.layout import resolve_vector_namespace
from madspec_cli.memory.shared.system_store.model_bootstrap import resolve_model_cache_root
from madspec_cli.memory.shared.system_store.sessions import save_runtime_session
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.shared.system_store.vector import VectorMemoryIndex

from tests.support import step_metadata, step_status, sync_branch_state, write_madspec_config


def _write_progress(paths, *, planned_steps: list[str], completed_steps: list[str]) -> None:
    write_json(
        paths.progress,
        {
            "currentImplementStep": None,
            "completedSteps": completed_steps,
            "plannedSteps": planned_steps,
            "stepStatus": {
                "step-01-bootstrap": step_status(
                    status="completed",
                    completed_at="2026-03-10T10:00:00+00:00",
                    tdd_phase="completed",
                    red=["uv run pytest tests/test_bootstrap.py -q"],
                    green=["uv run pytest tests/test_bootstrap.py -q"],
                    refactor_note="No refactor needed.",
                ),
                "step-02-auth-flow": step_status(status="planned"),
                "step-03-billing": step_status(status="planned"),
            },
            "stepMetadata": {
                "step-01-bootstrap": step_metadata("code", "required"),
                "step-02-auth-flow": step_metadata("code", "required"),
                "step-03-billing": step_metadata("code", "required"),
            },
            "coversFunctions": {
                "step-01-bootstrap": {"p1": ["Authentication"], "p2": [], "p3": []},
                "step-02-auth-flow": {"p1": ["Sessions"], "p2": [], "p3": []},
                "step-03-billing": {"p1": [], "p2": ["Billing"], "p3": []},
            },
            "planningMetadata": {
                "lastPlannedStep": "step-03-billing",
                "planningPhase": "initial",
                "totalStepsEstimated": 3,
                "stepDependencies": {
                    "step-02-auth-flow": ["step-01-bootstrap"],
                    "step-03-billing": ["step-02-auth-flow"],
                },
                "progressMetrics": {
                    "p1Coverage": {"covered": 2, "total": 2, "percentage": 100},
                    "p2Coverage": {"covered": 1, "total": 1, "percentage": 100},
                    "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                    "overallProgress": 80,
                },
            },
        },
    )


def _semantic_record(
    branch_name: str,
    stage: str,
    semantic_kind: str,
    summary: str,
    *,
    scope: str = "branch",
    record_id: str | None = None,
) -> dict[str, object]:
    record = make_record(
        branch_name,
        stage,
        "memory.promote",
        summary,
        status="validated",
        semantic_kind=semantic_kind,
        record_type=semantic_kind,
        scope=scope,
        metadata={"topic": summary},
    )
    if record_id is not None:
        record["id"] = record_id
    record["record_stream"] = {
        "fact": "facts",
        "decision": "decisions",
        "contract": "contracts",
    }[semantic_kind]
    return record


def _sync_paths(paths) -> None:
    sync_branch_state(paths.branch_dir.parents[1], paths.branch_dir.name)


def _inactive_semantic_chunk(namespace_dir, *, source_id: str, branch: str) -> None:
    index = VectorMemoryIndex(namespace_dir, provider_kind="hash", model_key="default", revision="legacy", dimension=64)
    index.upsert_chunks(
        "memory_chunks",
        [
            {
                "chunk_id": f"record:{source_id}:0",
                "source_type": "record",
                "source_id": source_id,
                "branch": branch,
                "stage": "mvp.plan",
                "step_id": None,
                "scope": "branch",
                "status": "validated",
                "kind": "fact",
                "content_hash": f"hash-{source_id}",
                "text": "inactive semantic residue",
                "snippet": "inactive semantic residue",
                "vector": [0.0] * 64,
            }
        ],
    )


def test_memory_why_next_step_and_explain_show_step_reasoning(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    paths = get_memory_paths(project_path, "main")
    _write_progress(
        paths,
        planned_steps=["step-01-bootstrap", "step-02-auth-flow", "step-03-billing"],
        completed_steps=["step-01-bootstrap"],
    )
    append_jsonl(
        paths.decisions,
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Validated planning decision",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
                evidence=["implementation-plan.md"],
            )
        ],
    )
    _sync_paths(paths)

    why_result = invoke_cli(
        ["memory", "why-next-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert why_result.exit_code == 0, why_result.stdout
    why_payload = json.loads(why_result.stdout)
    assert why_payload["selected_step"] == "step-02-auth-flow"
    steps = {item["step_id"]: item for item in why_payload["steps"]}
    assert steps["step-01-bootstrap"]["state"] == "completed"
    assert steps["step-02-auth-flow"]["state"] == "ready"
    assert steps["step-03-billing"]["state"] == "blocked"
    assert steps["step-03-billing"]["missing_dependencies"] == ["step-02-auth-flow"]
    assert steps["step-02-auth-flow"]["gate_summary"]["overall_status"] in {"passed", "warning", "pending"}
    assert "gates" in steps["step-02-auth-flow"]["gate_summary"]

    explain_result = invoke_cli(
        [
            "memory",
            "explain",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Validated planning decision",
            "--json-output",
        ]
    )
    assert explain_result.exit_code == 0, explain_result.stdout
    explain_payload = json.loads(explain_result.stdout)
    assert explain_payload["summary"]["selected_step"] == "step-02-auth-flow"
    assert explain_payload["recall_explanation"]["resolved_query"] == "Validated planning decision"
    assert explain_payload["gate_summary"]["overall_status"] in {"passed", "warning", "pending"}
    assert explain_payload["context"]["gate_summary"]["overall_status"] == explain_payload["gate_summary"]["overall_status"]
    assert "explicit_query" in explain_payload["recall_explanation"]["triggers"]
    influence_kinds = {item["kind"] for item in explain_payload["influences"]}
    assert "semantic_decision" in influence_kinds
    assert "recall_match" in influence_kinds
    assert explain_payload["observability"]["summary"]["projection_status"] in {"ok", "warn", "error"}
    assert explain_payload["observability"]["summary"]["semantic_integrity_status"] in {"ok", "warn", "error"}
    assert explain_payload["observability"]["summary"]["semantic_integrity_branch_issue_count"] >= 0

    why_text_result = invoke_cli(["memory", "why-next-step", "--branch", "main", "--stage", "mvp.implement"])
    assert why_text_result.exit_code == 0, why_text_result.stdout
    assert "Selected step:" in why_text_result.stdout
    assert "gates=" in why_text_result.stdout


def test_memory_explain_supports_session_local_focus(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    paths = get_memory_paths(project_path, "main")
    _write_progress(
        paths,
        planned_steps=["step-01-bootstrap", "step-02-auth-flow", "step-03-billing"],
        completed_steps=[],
    )
    payload = json.loads(paths.progress.read_text(encoding="utf-8"))
    payload["currentImplementStep"] = "step-01-bootstrap"
    payload["stepStatus"]["step-01-bootstrap"] = step_status(status="in_progress", tdd_phase="green")
    payload["planningMetadata"]["lastPlannedStep"] = "step-02-auth-flow"
    write_json(paths.progress, payload)
    _sync_paths(paths)

    load_canonical_branch_state(project_path, "main")
    save_runtime_session(
        project_path,
        branch_name="main",
        session_key="planner",
        payload={
            "branch": "main",
            "session_key": "planner",
            "stage": "mvp.plan",
            "current_step": "step-02-auth-flow",
            "active_goal": "Plan the next step",
            "open_questions": [],
            "pending_actions": [],
            "current_hypotheses": [],
            "last_checkpoint_at": "2026-03-10T10:00:00+00:00",
            "updated_at": "2026-03-10T10:00:00+00:00",
        },
    )
    save_runtime_session(
        project_path,
        branch_name="main",
        session_key="impl",
        payload={
            "branch": "main",
            "session_key": "impl",
            "stage": "mvp.implement",
            "current_step": "step-01-bootstrap",
            "active_goal": "Implement the current step",
            "open_questions": [],
            "pending_actions": [],
            "current_hypotheses": [],
            "last_checkpoint_at": "2026-03-10T10:05:00+00:00",
            "updated_at": "2026-03-10T10:05:00+00:00",
        },
    )

    planner_result = invoke_cli(
        [
            "memory",
            "explain",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--session-key",
            "planner",
            "--json-output",
        ]
    )
    impl_result = invoke_cli(
        [
            "memory",
            "explain",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--session-key",
            "impl",
            "--json-output",
        ]
    )

    assert planner_result.exit_code == 0, planner_result.stdout
    assert impl_result.exit_code == 0, impl_result.stdout

    planner_payload = json.loads(planner_result.stdout)
    impl_payload = json.loads(impl_result.stdout)

    assert planner_payload["summary"]["session_key"] == "planner"
    assert planner_payload["summary"]["session_current_step"] == "step-02-auth-flow"
    assert impl_payload["summary"]["session_key"] == "impl"
    assert impl_payload["summary"]["session_current_step"] == "step-01-bootstrap"
    assert planner_payload["summary"]["shared_current_implement_step"] == "step-01-bootstrap"
    assert impl_payload["summary"]["shared_current_implement_step"] == "step-01-bootstrap"
    assert planner_payload["summary"]["next_executable_step"] == "step-01-bootstrap"
    assert impl_payload["summary"]["next_executable_step"] == "step-01-bootstrap"
    assert planner_payload["summary"]["last_planned_step"] == "step-02-auth-flow"
    assert planner_payload["summary"]["planning_phase"] == "initial"
    assert planner_payload["summary"]["progress_metrics"]["p1Coverage"]["covered"] == 2


def test_memory_timeline_includes_progress_snapshot_and_retrieval_runs(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    paths = get_memory_paths(project_path, "main")
    _write_progress(
        paths,
        planned_steps=["step-01-bootstrap", "step-02-auth-flow", "step-03-billing"],
        completed_steps=["step-01-bootstrap"],
    )
    append_jsonl(
        paths.facts,
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Billing dependencies captured",
                status="validated",
                semantic_kind="fact",
                record_type="fact",
            )
        ],
    )

    search_result = invoke_cli(
        [
            "memory",
            "search",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Billing dependencies captured",
            "--json-output",
        ]
    )
    assert search_result.exit_code == 0, search_result.stdout

    timeline_result = invoke_cli(["memory", "timeline", "--branch", "main", "--stage", "mvp.plan", "--json-output"])
    assert timeline_result.exit_code == 0, timeline_result.stdout
    timeline_payload = json.loads(timeline_result.stdout)
    categories = {item["category"] for item in timeline_payload["items"]}
    assert "shared_commit" in categories
    assert "session_event" in categories
    retrieval_item = next(item for item in timeline_payload["items"] if item["source_type"] == "retrieval_run")
    assert retrieval_item["provider"] == "hash"
    assert retrieval_item["semantic_outcome"] == "used"
    assert timeline_payload["observability"]["embeddings"]["configured_embeddings"]["provider"] == "hash"
    assert timeline_payload["observability"]["summary"]["projection_status"] in {"ok", "warn", "error"}


def test_memory_doctor_reports_coordinator_issues(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    from tests.support import write_madspec_config

    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    init_memory_branch(branch="main", project_path=project_path)
    store = MemoryStore(project_path)
    task = store.create_task(branch="main", title="Coordinator task", summary=None, acceptance_note=None)
    work_item = store.create_work_item(
        branch="main",
        task_id=task["task_id"],
        title="Developer slice",
        work_item_type="implementation",
        subagent_id="developer",
        step_id="step-01-authentication",
        scope_descriptor={
            "step_id": "step-01-authentication",
            "paths": ["src/auth/service.py"],
            "artifacts": [],
            "concerns": ["implementation"],
        },
        acceptance_note=None,
    )
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO work_item_dependencies (
                dependency_id, branch, task_id, work_item_id, depends_on_work_item_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("dangling", "main", task["task_id"], work_item["work_item_id"], "missing-work-item", "2026-03-10T10:00:00+00:00"),
        )

    doctor_result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])
    assert doctor_result.exit_code == 1, doctor_result.stdout
    payload = json.loads(doctor_result.stdout)
    assert payload["coordinator"]["dangling_dependencies"][0]["depends_on_work_item_id"] == "missing-work-item"
    assert any(item["name"] == "coordinator" for item in payload["checks"])
    assert any(item["name"] == "orphan_sessions" for item in payload["checks"])
    assert any(item["name"] == "revision_drift" for item in payload["checks"])


def test_memory_inspect_record_and_conflicts_report_index_and_integrity(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    paths = get_memory_paths(project_path, "main")
    _write_progress(
        paths,
        planned_steps=["step-01-bootstrap", "step-02-auth-flow", "step-03-billing"],
        completed_steps=["step-01-bootstrap"],
    )
    inspected_record = make_record(
        "main",
        "mvp.plan",
        "agent",
        "Inspect me",
        status="validated",
        semantic_kind="decision",
        record_type="decision",
        evidence=["implementation-plan.md"],
    )
    conflicted_record = make_record(
        "main",
        "mvp.plan",
        "agent",
        "Conflicting billing note",
        status="conflicted",
        semantic_kind="fact",
        record_type="fact",
    )
    append_jsonl(paths.decisions, [inspected_record])
    append_jsonl(paths.facts, [conflicted_record])
    _sync_paths(paths)

    reindex_result = invoke_cli(["memory", "reindex", "--branch", "main", "--json-output"])
    assert reindex_result.exit_code == 0, reindex_result.stdout

    inspect_result = invoke_cli(
        [
            "memory",
            "inspect-record",
            "--branch",
            "main",
            "--id",
            inspected_record["id"],
            "--json-output",
        ]
    )
    assert inspect_result.exit_code == 0, inspect_result.stdout
    inspect_payload = json.loads(inspect_result.stdout)
    assert inspect_payload["found"] is True
    assert inspect_payload["record"]["payload"]["summary"] == "Inspect me"
    assert inspect_payload["source_file"].endswith("semantic/decisions.jsonl:1")
    assert inspect_payload["indexed"]["is_indexed"] is True

    (project_path / ".madspec" / "main" / "concept.md").write_text("# Drifted concept\n", encoding="utf-8")

    conflicts_result = invoke_cli(["memory", "conflicts", "--branch", "main", "--json-output"])
    assert conflicts_result.exit_code == 0, conflicts_result.stdout
    conflicts_payload = json.loads(conflicts_result.stdout)
    assert any(item["record_id"] == conflicted_record["id"] for item in conflicts_payload["record_conflicts"])
    assert conflicts_payload["integrity_conflicts"]
    assert conflicts_payload["conflict_dashboard"]["summary"]["total_conflicts"] >= 1

    missing_inspect = invoke_cli(
        ["memory", "inspect-record", "--branch", "main", "--id", "missing-record", "--json-output"]
    )
    assert missing_inspect.exit_code == 1, missing_inspect.stdout


def test_memory_doctor_reports_healthy_state_and_generated_view_drift(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")

    reindex_result = invoke_cli(["memory", "reindex", "--branch", "main", "--json-output"])
    assert reindex_result.exit_code == 0, reindex_result.stdout

    healthy_result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])
    assert healthy_result.exit_code == 0, healthy_result.stdout
    healthy_payload = json.loads(healthy_result.stdout)
    check_names = {item["name"] for item in healthy_payload["checks"]}
    assert {
        "branch_layout",
        "integrity",
        "sqlite",
        "vector",
        "indexing",
        "generated_views",
        "semantic_integrity_branch",
        "semantic_integrity_project",
        "semantic_integrity_active_namespace",
        "semantic_integrity_inactive_namespaces",
    } <= check_names
    assert healthy_payload["status"] in {"ok", "warn"}
    assert healthy_payload["semantic_integrity"]["status"] == "ok"
    assert healthy_payload["semantic_integrity"]["summary"]["error_count"] == 0
    assert set(healthy_payload["db"]) >= {"exists", "sqlite_path", "tables"}
    assert healthy_payload["observability"]["embeddings"]["configured_embeddings"]["provider"] == "hash"
    assert healthy_payload["observability"]["semantic_integrity"]["semantic_integrity_status"] == "ok"
    assert set(healthy_payload["vector"]) >= {
        "backend",
        "memory_chunk_count",
        "artifact_chunk_count",
        "vector_root_dir",
        "vector_dir",
        "active_vector_namespace",
        "legacy_flat_layout",
    }
    assert healthy_payload["vector"]["vector_root_dir"] == ".madspec/system/memory/lancedb"
    assert healthy_payload["vector"]["vector_dir"] == ".madspec/system/memory/lancedb/hash/default/current/64"
    assert healthy_payload["vector"]["active_vector_namespace"] == ".madspec/system/memory/lancedb/hash/default/current/64"
    assert healthy_payload["vector"]["legacy_flat_layout"] is False

    (project_path / ".madspec" / "main" / "concept.md").write_text("# Drifted concept\n", encoding="utf-8")

    drift_result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])
    assert drift_result.exit_code == 1, drift_result.stdout
    drift_payload = json.loads(drift_result.stdout)
    assert drift_payload["status"] == "error"
    assert drift_payload["generated_views"]["status"] == "error"
    stale_check = {item["name"]: item for item in drift_payload["checks"]}["stale_projections"]
    assert stale_check["status"] == "error"
    assert stale_check["probable_cause"]

    doctor_text_result = invoke_cli(["memory", "doctor", "--branch", "main"])
    assert doctor_text_result.exit_code == 1, doctor_text_result.stdout
    assert "Overall status:" in doctor_text_result.stdout


def test_memory_doctor_reports_semantic_branch_projection_drift(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    store = MemoryStore(project_path)
    paths = get_memory_paths(project_path, "main")
    fact = _semantic_record("main", "mvp.plan", "fact", "Canonical semantic fact")
    store.upsert_records_batch([fact])

    paths.facts.write_text("", encoding="utf-8")

    result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    branch_issues = payload["semantic_integrity"]["branch"]["issues"]
    assert any(item["code"] == "semantic_branch_projection_drift" for item in branch_issues)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["semantic_integrity_branch"]["status"] == "error"


def test_memory_doctor_reports_project_semantic_shape_and_id_mismatch(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    store = MemoryStore(project_path)
    project_record = _semantic_record(
        PROJECT_MEMORY_BRANCH,
        "mvp.plan",
        "decision",
        "Broken promoted project decision",
        scope="branch",
        record_id="manual-project-record-id",
    )
    store.upsert_records_batch([project_record])

    result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    project_issues = payload["semantic_integrity"]["project"]["issues"]
    issue_codes = {item["code"] for item in project_issues}
    assert "semantic_project_id_mismatch" in issue_codes
    assert "semantic_project_scope_mismatch" in issue_codes
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["semantic_integrity_project"]["status"] == "error"


def test_memory_doctor_reports_semantic_active_chunk_orphan(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    store = MemoryStore(project_path)
    fact = _semantic_record("main", "mvp.plan", "fact", "Index me before orphaning")
    store.upsert_records_batch([fact])
    store.process_pending_jobs(rebuild=True, limit=500)
    store.delete_records([str(fact["id"])])

    result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    active_issues = payload["semantic_integrity"]["active_vector_namespace"]["issues"]
    assert any(item["code"] == "semantic_active_chunk_orphan" for item in active_issues)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["semantic_integrity_active_namespace"]["status"] == "error"


def test_memory_doctor_warns_about_inactive_semantic_namespace_residue(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    inactive_namespace = resolve_vector_namespace(
        project_path,
        provider="hash",
        model="default",
        revision="legacy",
        dimension=64,
    )
    _inactive_semantic_chunk(
        inactive_namespace.namespace_dir,
        source_id="ghost-semantic-record",
        branch="main",
    )

    result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    inactive_issues = payload["semantic_integrity"]["inactive_vector_namespaces"]["issues"]
    assert any(item["code"] == "semantic_inactive_namespace_residue" for item in inactive_issues)
    assert payload["semantic_integrity"]["inactive_vector_namespaces"]["status"] == "warn"
    assert any("madspec memory gc vector-namespaces" in item["repair_hint"] for item in inactive_issues)
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["semantic_integrity_inactive_namespaces"]["status"] == "warn"


def test_memory_gc_vector_namespaces_dry_run_and_delete(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    inactive_namespace = resolve_vector_namespace(
        project_path,
        provider="hash",
        model="default",
        revision="legacy",
        dimension=64,
    )
    _inactive_semantic_chunk(
        inactive_namespace.namespace_dir,
        source_id="ghost-semantic-record",
        branch="main",
    )

    dry_run = invoke_cli(["memory", "gc", "vector-namespaces", "--dry-run", "--json-output"])
    assert dry_run.exit_code == 0, dry_run.stdout
    dry_payload = json.loads(dry_run.stdout)
    assert dry_payload["dry_run"] is True
    assert dry_payload["candidates"][0]["path"] == str(inactive_namespace.namespace_dir.relative_to(project_path))
    assert dry_payload["candidates"][0]["semantic_chunk_count"] > 0
    assert inactive_namespace.namespace_dir.exists()

    gc_result = invoke_cli(["memory", "gc", "vector-namespaces", "--json-output"])
    assert gc_result.exit_code == 0, gc_result.stdout
    gc_payload = json.loads(gc_result.stdout)
    assert gc_payload["deleted_namespaces"] == [str(inactive_namespace.namespace_dir.relative_to(project_path))]
    assert gc_payload["deleted_chunk_count"] > 0
    assert not inactive_namespace.namespace_dir.exists()

    doctor_result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])
    assert doctor_result.exit_code == 0, doctor_result.stdout
    doctor_payload = json.loads(doctor_result.stdout)
    assert doctor_payload["semantic_integrity"]["inactive_vector_namespaces"]["issues"] == []


def test_memory_doctor_warns_about_legacy_flat_vector_layout(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    legacy_root = project_path / ".madspec" / "system" / "memory" / "lancedb"
    (legacy_root / "memory_chunks.jsonl").write_text("", encoding="utf-8")

    result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["vector"]["legacy_flat_layout"] is True
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["vector"]["status"] == "warn"
    assert any("legacy flat vector layout detected" in detail for detail in checks["vector"]["details"])


def test_memory_doctor_reports_missing_dense_model_cache(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "dense-missing"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    config_path = project_path / ".madspec" / "config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "none",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    init_memory_branch(branch="main", project_path=project_path)

    result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])

    assert result.exit_code == 1, result.stdout
    doctor_payload = json.loads(result.stdout)
    embeddings_check = {item["name"]: item for item in doctor_payload["checks"]}["embeddings"]
    assert embeddings_check["status"] == "error"
    assert doctor_payload["embeddings_status"]["configured_embeddings"]["status"] == "missing"
    assert embeddings_check["repair_hint"] == "Run `madspec memory bootstrap-model`, then `madspec memory reindex`."


def test_memory_doctor_warns_when_active_namespace_needs_reindex(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = tmp_path / "dense-reindex"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    init_memory_branch(branch="main", project_path=project_path)

    reindex_result = invoke_cli(["memory", "reindex", "--branch", "main", "--json-output"])
    assert reindex_result.exit_code == 0, reindex_result.stdout

    config_path = project_path / ".madspec" / "config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    cache_root = resolve_model_cache_root(project_path, ".madspec/system/models", "multilingual-e5-small", None)
    snapshot_dir = cache_root / "snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "model.onnx").write_text("placeholder", encoding="utf-8")
    (cache_root / "manifest.json").write_text(
        json.dumps(
            {
                "providerKind": "local-hf-onnx",
                "modelKey": "multilingual-e5-small",
                "requestedRevision": None,
                "resolvedRevision": "current",
                "hfRepoId": "intfloat/multilingual-e5-small",
                "dimension": 384,
                "localPath": str(snapshot_dir.relative_to(project_path)),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])

    assert result.exit_code == 0, result.stdout
    doctor_payload = json.loads(result.stdout)
    embeddings_check = {item["name"]: item for item in doctor_payload["checks"]}["embeddings"]
    assert embeddings_check["status"] == "warn"
    assert doctor_payload["embeddings_status"]["configured_embeddings"]["status"] == "ready"
    assert doctor_payload["embeddings_status"]["index_state"]["reindexRequired"] is True
    assert doctor_payload["embeddings_status"]["index_state"]["reason"] == "namespace_mismatch"


def test_memory_doctor_reports_active_and_expired_writer_leases(init_memory_branch, invoke_cli) -> None:
    project_path = init_memory_branch(branch="main")
    store = MemoryStore(project_path)

    active = store.acquire_lease("plan-catalog:main", "planner-owner", ttl_seconds=30)
    expired = store.acquire_lease("review:main", "review-owner", ttl_seconds=0)
    assert active["acquired"] is True
    assert expired["acquired"] is True

    result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    writer_leases = payload["writer_leases"]
    assert any(item["lease_name"] == "plan-catalog:main" and item["expired"] is False for item in writer_leases["leases"])
    assert any(item["lease_name"] == "review:main" and item["expired"] is True for item in writer_leases["leases"])
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["writer_leases"]["status"] == "warn"
    assert checks["stuck_leases"]["status"] == "warn"
