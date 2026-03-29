from __future__ import annotations

import json

from madspec_cli.memory.shared.records import make_record
from madspec_cli.memory.shared.storage import ensure_memory_layout
from madspec_cli.memory.shared.system_store import refresh_branch_projections
from madspec_cli.memory.shared.system_store.sessions import save_runtime_session
from madspec_cli.memory.shared.system_store.store import MemoryStore

from tests.support import create_step_artifacts, write_concept_markdown, write_madspec_config


def _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch):
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent", phase2_enabled=True)
    init_memory_branch(branch="main", project_path=project_path)
    return project_path


def _create_claim(
    invoke_cli,
    *,
    task_title: str,
    work_title: str,
    subagent_id: str,
    session_key: str,
    step_id: str | None,
    path: str | None = None,
):
    task_result = invoke_cli(
        [
            "memory",
            "tasks",
            "create",
            "--branch",
            "main",
            "--title",
            task_title,
            "--json-output",
        ]
    )
    assert task_result.exit_code == 0, task_result.stdout
    task_payload = json.loads(task_result.stdout)
    args = [
        "memory",
        "work-items",
        "create",
        "--branch",
        "main",
        "--task-id",
        task_payload["task"]["task_id"],
        "--title",
        work_title,
        "--type",
        "implementation",
        "--subagent-id",
        subagent_id,
        "--json-output",
    ]
    if step_id:
        args.extend(["--step-id", step_id])
    if path:
        args.extend(["--path", path])
    work_item_result = invoke_cli(args)
    assert work_item_result.exit_code == 0, work_item_result.stdout
    work_item_payload = json.loads(work_item_result.stdout)
    claim_result = invoke_cli(
        [
            "memory",
            "work-items",
            "claim",
            "--branch",
            "main",
            "--work-item-id",
            work_item_payload["work_item"]["work_item_id"],
            "--session-key",
            session_key,
            "--subagent-id",
            subagent_id,
            "--json-output",
        ]
    )
    assert claim_result.exit_code == 0, claim_result.stdout
    return task_payload, work_item_payload


def _seed_branch_semantic(project_path, branch_name: str) -> dict[str, list[dict[str, object]]]:
    ensure_memory_layout(project_path, branch_name, full=True)
    store = MemoryStore(project_path)
    facts = [
        _semantic_record(
            branch_name,
            "mvp.plan",
            "fact",
            "Keep current leaderboard snapshot for replay",
            source="memory.promote",
            metadata={"topic": "leaderboard", "variant": "canonical"},
        ),
        _semantic_record(
            branch_name,
            "mvp.plan",
            "fact",
            "Keep current leaderboard snapshot for replay",
            source="memory.promote",
            metadata={"topic": "leaderboard", "variant": "duplicate"},
        ),
    ]
    decisions = [
        _semantic_record(
            branch_name,
            "mvp.plan",
            "decision",
            "Resolve matchmaking before prize distribution",
            source="memory.promote",
            metadata={"priority": "p1"},
        )
    ]
    contracts = [
        _semantic_record(
            branch_name,
            "mvp.architecture",
            "contract",
            "POST /matches must return replay token",
            source="memory.promote",
            metadata={"endpoint": "POST /matches"},
        )
    ]
    store.upsert_records_batch([*facts, *decisions, *contracts])
    refresh_branch_projections(project_path, branch_name, full=True)
    return {"facts": facts, "decisions": decisions, "contracts": contracts}


def _semantic_record(
    branch_name: str,
    stage: str,
    semantic_kind: str,
    summary: str,
    *,
    source: str,
    metadata: dict[str, object],
) -> dict[str, object]:
    record = make_record(
        branch_name,
        stage,
        source,
        summary,
        status="validated",
        evidence=[f"{stage}:{semantic_kind}"],
        scope="branch",
        semantic_kind=semantic_kind,
        record_type=semantic_kind,
        metadata=metadata,
    )
    record["record_stream"] = {
        "fact": "facts",
        "decision": "decisions",
        "contract": "contracts",
    }[semantic_kind]
    return record


def test_memory_proposals_publish_list_preview_apply_plan_change(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    branch_dir = project_path / ".madspec" / "main"
    write_concept_markdown(branch_dir, variant="auth_profile_export")
    sync_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert sync_result.exit_code == 0, sync_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")
    task_payload, work_item_payload = _create_claim(
        invoke_cli,
        task_title="Coordinate planning",
        work_title="Developer planning slice",
        subagent_id="developer",
        session_key="impl",
        step_id="step-01-authentication",
        path="src/auth/service.py",
    )

    store = MemoryStore(project_path)
    base_revision = store.fetch_branch_revision("main")
    publish_result = invoke_cli(
        [
            "memory",
            "proposals",
            "publish",
            "--branch",
            "main",
            "--type",
            "plan_change",
            "--session-key",
            "impl",
            "--subagent-id",
            "developer",
            "--base-revision",
            str(base_revision),
            "--payload-json",
            json.dumps(
                {
                    "stage": "mvp.plan",
                    "step_id": "step-01-authentication",
                    "covers": ["Authentication"],
                    "step_kind": "code",
                }
            ),
            "--target-scope-json",
            json.dumps({"scope": "plan-catalog", "step_id": "step-01-authentication"}),
            "--json-output",
        ]
    )
    assert publish_result.exit_code == 0, publish_result.stdout
    publish_payload = json.loads(publish_result.stdout)
    proposal_id = publish_payload["proposal"]["proposal_id"]

    list_result = invoke_cli(
        [
            "memory",
            "proposals",
            "list",
            "--branch",
            "main",
            "--work-item-id",
            work_item_payload["work_item"]["work_item_id"],
            "--json-output",
        ]
    )
    assert list_result.exit_code == 0, list_result.stdout
    listed = json.loads(list_result.stdout)
    assert listed["proposals"][0]["proposal_id"] == proposal_id

    preview_result = invoke_cli(
        [
            "memory",
            "proposals",
            "preview",
            "--proposal-id",
            proposal_id,
            "--json-output",
        ]
    )
    assert preview_result.exit_code == 0, preview_result.stdout
    preview_payload = json.loads(preview_result.stdout)
    assert preview_payload["ownership"]["valid"] is True
    assert preview_payload["summary"]["work_item_id"] == work_item_payload["work_item"]["work_item_id"]

    apply_result = invoke_cli(
        [
            "memory",
            "proposals",
            "apply",
            "--proposal-id",
            proposal_id,
            "--json-output",
        ]
    )
    assert apply_result.exit_code == 0, apply_result.stdout
    apply_payload = json.loads(apply_result.stdout)
    assert apply_payload["proposal"]["status"] == "applied"
    assert apply_payload["apply_result"]["accepted"] is True

    explain_result = invoke_cli(
        [
            "memory",
            "explain",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--session-key",
            "impl",
            "--json-output",
        ]
    )
    assert explain_result.exit_code == 0, explain_result.stdout
    explain_payload = json.loads(explain_result.stdout)
    assert explain_payload["latest_runtime_outcome"]["outcome"] == "merged"
    assert explain_payload["observability"]["proposal_state"]["latest"]["status"] == "applied"

    timeline_result = invoke_cli(["memory", "timeline", "--branch", "main", "--json-output"])
    assert timeline_result.exit_code == 0, timeline_result.stdout
    timeline_payload = json.loads(timeline_result.stdout)
    assert any(item["category"] == "auto_merge" for item in timeline_payload["items"])

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--session-key",
            "impl",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert "step-01-authentication" in retrieve_payload["workflow"]["plannedSteps"]
    assert retrieve_payload["coordination"]["proposal_summary"]["last_proposal_status"] == "applied"

    context_result = invoke_cli(
        [
            "agents",
            "subagents",
            "context",
            "--subagent-id",
            "developer",
            "--session-key",
            "impl",
            "--json-output",
        ]
    )
    assert context_result.exit_code == 0, context_result.stdout
    context_payload = json.loads(context_result.stdout)
    assert context_payload["proposal_summary"]["last_proposal_status"] == "applied"
    assert context_payload["coordination"]["task"]["task_id"] == task_payload["task"]["task_id"]


def test_claimed_session_direct_runtime_write_is_blocked(tmp_path, monkeypatch, invoke_cli, init_memory_branch) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    branch_dir = project_path / ".madspec" / "main"
    write_concept_markdown(branch_dir, variant="auth_profile_export")
    sync_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert sync_result.exit_code == 0, sync_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")
    _create_claim(
        invoke_cli,
        task_title="Coordinate planning",
        work_title="Developer planning slice",
        subagent_id="developer",
        session_key="impl",
        step_id="step-01-authentication",
        path="src/auth/service.py",
    )

    result = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--session-key",
            "impl",
            "--step-id",
            "step-01-authentication",
            "--step-kind",
            "code",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )
    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert "must use proposal-based writes" in payload["errors"][0]
    assert payload["proposal_required"]["recommended_command"].startswith("madspec memory proposals publish")


def test_memory_proposals_runtime_conflict_and_ownership_violation(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    branch_dir = project_path / ".madspec" / "main"
    write_concept_markdown(branch_dir, variant="auth_sessions")
    sync_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert sync_result.exit_code == 0, sync_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")

    register_result = invoke_cli(
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
        ]
    )
    assert register_result.exit_code == 0, register_result.stdout
    start_result = invoke_cli(
        [
            "memory",
            "start-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--json-output",
        ]
    )
    assert start_result.exit_code == 0, start_result.stdout

    _, work_item_payload = _create_claim(
        invoke_cli,
        task_title="Coordinate implementation",
        work_title="Developer implementation slice",
        subagent_id="developer",
        session_key="impl",
        step_id="step-01-authentication",
        path="src/auth/service.py",
    )
    store = MemoryStore(project_path)
    base_revision = store.fetch_branch_revision("main")

    publish_result = invoke_cli(
        [
            "memory",
            "proposals",
            "publish",
            "--branch",
            "main",
            "--type",
            "runtime_step_update",
            "--session-key",
            "impl",
            "--subagent-id",
            "developer",
            "--base-revision",
            str(base_revision),
            "--payload-json",
            json.dumps(
                {
                    "stage": "mvp.implement",
                    "operation": "checkpoint-step",
                    "step_id": "step-01-authentication",
                    "summary": "Checkpoint from proposal",
                    "tdd_phase": "red",
                    "red_evidence": ["uv run pytest tests/test_auth.py -q"],
                }
            ),
            "--target-scope-json",
            json.dumps({"scope": "step", "step_id": "step-01-authentication"}),
            "--json-output",
        ]
    )
    assert publish_result.exit_code == 0, publish_result.stdout
    proposal_id = json.loads(publish_result.stdout)["proposal"]["proposal_id"]

    direct_checkpoint = invoke_cli(
        [
            "memory",
            "checkpoint-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-authentication",
            "--summary",
            "Fresh checkpoint",
            "--tdd-phase",
            "red",
            "--red-evidence",
            "uv run pytest tests/test_auth.py -q",
            "--json-output",
        ]
    )
    assert direct_checkpoint.exit_code == 0, direct_checkpoint.stdout

    apply_conflict = invoke_cli(
        [
            "memory",
            "proposals",
            "apply",
            "--proposal-id",
            proposal_id,
            "--json-output",
        ]
    )
    assert apply_conflict.exit_code == 1, apply_conflict.stdout
    conflict_payload = json.loads(apply_conflict.stdout)
    assert conflict_payload["proposal"]["status"] == "conflict"
    assert conflict_payload["proposal"]["apply_summary"]["reason"] in {"stale_revision", "scope_conflict"}

    publish_ownership = invoke_cli(
        [
            "memory",
            "proposals",
            "publish",
            "--branch",
            "main",
            "--type",
            "semantic_update",
            "--session-key",
            "impl",
            "--subagent-id",
            "developer",
            "--base-revision",
            str(store.fetch_branch_revision("main")),
            "--payload-json",
            json.dumps(
                {
                    "stage": "mvp.tech",
                    "operation": "capture",
                    "facts": ["Redis caches active sessions"],
                }
            ),
            "--target-scope-json",
            json.dumps({"scope": "work-item"}),
            "--json-output",
        ]
    )
    assert publish_ownership.exit_code == 0, publish_ownership.stdout
    ownership_proposal_id = json.loads(publish_ownership.stdout)["proposal"]["proposal_id"]

    release_result = invoke_cli(
        [
            "memory",
            "work-items",
            "release",
            "--branch",
            "main",
            "--work-item-id",
            work_item_payload["work_item"]["work_item_id"],
            "--session-key",
            "impl",
            "--json-output",
        ]
    )
    assert release_result.exit_code == 0, release_result.stdout

    apply_rejected = invoke_cli(
        [
            "memory",
            "proposals",
            "apply",
            "--proposal-id",
            ownership_proposal_id,
            "--json-output",
        ]
    )
    assert apply_rejected.exit_code == 1, apply_rejected.stdout
    rejected_payload = json.loads(apply_rejected.stdout)
    assert rejected_payload["proposal"]["status"] == "rejected"
    assert rejected_payload["proposal"]["apply_summary"]["reason"] == "ownership_violation"


def test_memory_proposals_publish_and_apply_semantic_cleanup(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    seeded = _seed_branch_semantic(project_path, "main")
    _, work_item_payload = _create_claim(
        invoke_cli,
        task_title="Coordinate semantic cleanup",
        work_title="Cleanup semantic branch knowledge",
        subagent_id="developer",
        session_key="cleanup",
        step_id=None,
        path="semantic/facts.jsonl",
    )
    store = MemoryStore(project_path)
    base_revision = store.fetch_branch_revision("main")

    publish_result = invoke_cli(
        [
            "memory",
            "proposals",
            "publish",
            "--branch",
            "main",
            "--type",
            "semantic_cleanup",
            "--session-key",
            "cleanup",
            "--subagent-id",
            "developer",
            "--base-revision",
            str(base_revision),
            "--payload-json",
            json.dumps(
                {
                    "scope": "branch",
                    "operation": "prune",
                    "summary": "Prune duplicate semantic fact",
                    "operations": [
                        {
                            "semantic_kind": "fact",
                            "record_id": seeded["facts"][1]["id"],
                        }
                    ],
                }
            ),
            "--json-output",
        ]
    )
    assert publish_result.exit_code == 0, publish_result.stdout
    publish_payload = json.loads(publish_result.stdout)
    proposal = publish_payload["proposal"]
    proposal_id = proposal["proposal_id"]
    assert proposal["proposal_type"] == "semantic_cleanup"
    assert proposal["target_scope"] == {"scope": "semantic-knowledge"}
    assert proposal["work_item_id"] == work_item_payload["work_item"]["work_item_id"]

    apply_result = invoke_cli(
        [
            "memory",
            "proposals",
            "apply",
            "--proposal-id",
            proposal_id,
            "--json-output",
        ]
    )
    assert apply_result.exit_code == 0, apply_result.stdout
    apply_payload = json.loads(apply_result.stdout)
    assert apply_payload["proposal"]["status"] == "applied"
    assert apply_payload["apply_result"]["accepted"] is True
    assert apply_payload["apply_result"]["details"]["removed_count"] == 1

    retrieve_result = invoke_cli(
        [
            "memory",
            "semantic",
            "retrieve",
            "--scope",
            "branch",
            "--branch",
            "main",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    fact_ids = {item["id"] for item in retrieve_payload["semantic"]["facts"]}
    assert seeded["facts"][1]["id"] not in fact_ids


def test_memory_proposals_show_up_in_timeline_and_doctor(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    branch_dir = project_path / ".madspec" / "main"
    write_concept_markdown(branch_dir, variant="auth_profile_export")
    sync_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert sync_result.exit_code == 0, sync_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")
    _, work_item_payload = _create_claim(
        invoke_cli,
        task_title="Coordinate planning",
        work_title="Developer planning slice",
        subagent_id="developer",
        session_key="impl",
        step_id="step-01-authentication",
        path="src/auth/service.py",
    )
    base_revision = MemoryStore(project_path).fetch_branch_revision("main")
    publish_result = invoke_cli(
        [
            "memory",
            "proposals",
            "publish",
            "--branch",
            "main",
            "--type",
            "plan_change",
            "--session-key",
            "impl",
            "--subagent-id",
            "developer",
            "--base-revision",
            str(base_revision),
            "--payload-json",
            json.dumps(
                {
                    "stage": "mvp.plan",
                    "step_id": "step-01-authentication",
                    "covers": ["Authentication"],
                    "step_kind": "code",
                }
            ),
            "--target-scope-json",
            json.dumps({"scope": "plan-catalog", "step_id": "step-01-authentication"}),
            "--json-output",
        ]
    )
    assert publish_result.exit_code == 0, publish_result.stdout
    proposal_id = json.loads(publish_result.stdout)["proposal"]["proposal_id"]

    timeline_result = invoke_cli(
        [
            "memory",
            "timeline",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--json-output",
        ]
    )
    assert timeline_result.exit_code == 0, timeline_result.stdout
    timeline_payload = json.loads(timeline_result.stdout)
    assert any(
        item["source_type"] == "proposal_event" and "Published" in item["summary"]
        for item in timeline_payload["items"]
    )

    doctor_result = invoke_cli(["memory", "doctor", "--branch", "main", "--json-output"])
    assert doctor_result.exit_code == 0, doctor_result.stdout
    doctor_payload = json.loads(doctor_result.stdout)
    assert doctor_payload["runtime_proposals"]["pending_proposals"] == 1
    assert any(item["name"] == "runtime_proposals" for item in doctor_payload["checks"])

    preview_result = invoke_cli(
        [
            "memory",
            "proposals",
            "preview",
            "--proposal-id",
            proposal_id,
            "--json-output",
        ]
    )
    assert preview_result.exit_code == 0, preview_result.stdout
    preview_payload = json.loads(preview_result.stdout)
    assert preview_payload["proposal"]["work_item_id"] == work_item_payload["work_item"]["work_item_id"]


def test_memory_proposal_apply_rejected_when_coordinator_readiness_is_blocked(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    branch_dir = project_path / ".madspec" / "main"
    write_concept_markdown(branch_dir, variant="auth_profile_export")
    sync_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert sync_result.exit_code == 0, sync_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")

    task_result = invoke_cli(["memory", "tasks", "create", "--branch", "main", "--title", "Coordinate auth", "--json-output"])
    task_payload = json.loads(task_result.stdout)
    dependency_result = invoke_cli(
        [
            "memory",
            "work-items",
            "create",
            "--branch",
            "main",
            "--task-id",
            task_payload["task"]["task_id"],
            "--title",
            "Architecture slice",
            "--type",
            "architecture",
            "--subagent-id",
            "architecture",
            "--step-id",
            "step-01-authentication",
            "--path",
            "src/auth/contracts.py",
            "--json-output",
        ]
    )
    dependency_payload = json.loads(dependency_result.stdout)
    blocker_result = invoke_cli(
        [
            "memory",
            "work-items",
            "create",
            "--branch",
            "main",
            "--task-id",
            task_payload["task"]["task_id"],
            "--title",
            "Testing blocker",
            "--type",
            "testing",
            "--subagent-id",
            "testing",
            "--step-id",
            "step-01-authentication",
            "--path",
            "tests/test_auth.py",
            "--json-output",
        ]
    )
    claim_result = invoke_cli(
        [
            "memory",
            "work-items",
            "claim",
            "--branch",
            "main",
            "--work-item-id",
            dependency_payload["work_item"]["work_item_id"],
            "--session-key",
            "arch",
            "--subagent-id",
            "architecture",
            "--json-output",
        ]
    )
    assert claim_result.exit_code == 0, claim_result.stdout

    store = MemoryStore(project_path)
    ts = store.fetch_branch_revision("main")
    publish_result = invoke_cli(
        [
            "memory",
            "proposals",
            "publish",
            "--branch",
            "main",
            "--type",
            "semantic_update",
            "--session-key",
            "arch",
            "--subagent-id",
            "architecture",
            "--base-revision",
            str(ts),
            "--payload-json",
            json.dumps({"stage": "mvp.architecture", "operation": "capture", "facts": ["Contract updated"]}),
            "--target-scope-json",
            json.dumps({"scope": "work-item", "step_id": "step-01-authentication"}),
            "--json-output",
        ]
    )
    proposal_id = json.loads(publish_result.stdout)["proposal"]["proposal_id"]
    blocker_payload = json.loads(blocker_result.stdout)
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO work_item_dependencies (
                dependency_id, branch, task_id, work_item_id, depends_on_work_item_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "proposal-blocker",
                "main",
                task_payload["task"]["task_id"],
                dependency_payload["work_item"]["work_item_id"],
                blocker_payload["work_item"]["work_item_id"],
                "2026-03-10T10:00:00+00:00",
            ),
        )
    apply_result = invoke_cli(["memory", "proposals", "apply", "--proposal-id", proposal_id, "--json-output"])
    assert apply_result.exit_code == 1, apply_result.stdout
    payload = json.loads(apply_result.stdout)
    assert payload["proposal"]["apply_summary"]["reason"] == "readiness_blocked"


def test_memory_proposals_are_blocked_when_phase2_is_disabled(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent", phase2_enabled=False)
    init_memory_branch(branch="main", project_path=project_path)

    result = invoke_cli(
        [
            "memory",
            "proposals",
            "list",
            "--branch",
            "main",
            "--json-output",
        ]
    )

    assert result.exit_code == 1, result.stdout
    payload = json.loads(result.stdout)
    assert payload["reason"] == "phase2_disabled"
    assert payload["message"] == "Phase 2 coordinator runtime is disabled for this project"


def test_direct_runtime_write_still_works_when_phase2_is_disabled_even_with_claimed_state(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = tmp_path / "demo"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent", phase2_enabled=False)
    init_memory_branch(branch="main", project_path=project_path)

    branch_dir = project_path / ".madspec" / "main"
    write_concept_markdown(branch_dir, variant="auth_profile_export")
    sync_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert sync_result.exit_code == 0, sync_result.stdout
    create_step_artifacts(branch_dir, "step-01-authentication")

    store = MemoryStore(project_path)
    task = store.create_task(branch="main", title="Hidden phase2 task", summary=None, acceptance_note=None)
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
    store.claim_work_item(
        branch="main",
        work_item_id=work_item["work_item_id"],
        session_key="impl",
        subagent_id="developer",
    )
    save_runtime_session(
        project_path,
        branch_name="main",
        session_key="impl",
        payload={
            "branch": "main",
            "session_key": "impl",
            "stage": "mvp.plan",
            "current_step": None,
            "task_id": task["task_id"],
            "work_item_id": work_item["work_item_id"],
            "subagent_id": "developer",
            "open_questions": [],
            "pending_actions": [],
            "current_hypotheses": [],
        },
    )

    result = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--session-key",
            "impl",
            "--step-id",
            "step-01-authentication",
            "--step-kind",
            "code",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
