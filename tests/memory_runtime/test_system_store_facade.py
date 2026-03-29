from __future__ import annotations

from madspec_cli.memory.shared.system_store.db import SystemStoreDB
from madspec_cli.memory.shared.system_store.index_store import IndexStore
from madspec_cli.memory.shared.system_store.proposal_store import ProposalStore
from madspec_cli.memory.shared.system_store.runtime_store import RuntimeStore
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.shared.system_store.task_store import TaskStore


def test_system_store_db_schema_is_idempotent_and_read_only_uses_same_sqlite_file(memory_project) -> None:
    db = SystemStoreDB(memory_project.project_path)

    db.ensure_schema()
    db.ensure_schema()

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO branch_runtime_state (branch, revision, updated_at)
            VALUES ('main', 7, '2026-03-29T00:00:00+00:00')
            ON CONFLICT(branch) DO UPDATE SET revision = excluded.revision, updated_at = excluded.updated_at
            """
        )

    with db.connect_read_only() as conn:
        row = conn.execute(
            "SELECT revision FROM branch_runtime_state WHERE branch = ?",
            ("main",),
        ).fetchone()

    assert db.paths.sqlite_file.exists()
    assert row is not None
    assert row["revision"] == 7


def test_memory_store_facade_exposes_bounded_context_components(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)

    assert isinstance(store.runtime, RuntimeStore)
    assert isinstance(store.tasks, TaskStore)
    assert isinstance(store.proposals, ProposalStore)
    assert isinstance(store.index, IndexStore)
    assert store.paths.sqlite_file == store.db.paths.sqlite_file


def test_runtime_store_round_trip_sessions_revisions_and_leases(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)

    store.runtime.upsert_session(
        branch="main",
        session_key="planner",
        payload={
            "branch": "main",
            "stage": "mvp.plan",
            "current_step": "step-01-auth",
            "updated_at": "2026-03-29T00:00:00+00:00",
        },
    )
    store.runtime.update_branch_revision("main", revision=3)
    acquired = store.runtime.acquire_lease(lease_name="runtime-writer", owner_id="planner")
    leases = store.runtime.list_writer_leases()
    released = store.runtime.release_lease(lease_name="runtime-writer", owner_id="planner")

    assert store.fetch_session(branch="main", session_key="planner") == {
        "branch": "main",
        "stage": "mvp.plan",
        "current_step": "step-01-auth",
        "updated_at": "2026-03-29T00:00:00+00:00",
    }
    assert store.fetch_branch_revision("main") == 3
    assert acquired["acquired"] is True
    assert acquired["lease"]["lease_name"] == "runtime-writer"
    assert any(item["lease_name"] == "runtime-writer" for item in leases)
    assert released is None


def test_task_store_round_trip_dependencies_and_coordination(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)

    task = store.create_task(
        branch="main",
        title="Coordinate authentication rollout",
        summary="Track auth work items",
        acceptance_note=None,
    )
    prereq = store.create_work_item(
        branch="main",
        task_id=task["task_id"],
        title="Define auth scope",
        work_item_type="research",
        subagent_id="planner",
        step_id="step-01-auth",
        scope_descriptor={"paths": ["docs/auth.md"]},
    )
    dependent = store.create_work_item(
        branch="main",
        task_id=task["task_id"],
        title="Implement auth flow",
        work_item_type="implementation",
        subagent_id="builder",
        step_id="step-01-auth",
        scope_descriptor={"paths": ["src/auth.py"]},
        depends_on_work_item_ids=[prereq["work_item_id"]],
    )
    store.runtime.upsert_session(
        branch="main",
        session_key="planner-session",
        payload={
            "branch": "main",
            "task_id": task["task_id"],
            "work_item_id": prereq["work_item_id"],
            "subagent_id": "planner",
            "updated_at": "2026-03-29T00:01:00+00:00",
        },
    )
    claim = store.claim_work_item(
        branch="main",
        work_item_id=prereq["work_item_id"],
        session_key="planner-session",
        subagent_id="planner",
    )
    dependencies = store.list_work_item_dependencies(task_id=task["task_id"])
    explanation = store.explain_work_item(branch="main", work_item_id=dependent["work_item_id"])
    coordination = store.fetch_session_coordination(branch="main", session_key="planner-session")

    assert store.fetch_task(task["task_id"]) is not None
    assert store.fetch_work_item(prereq["work_item_id"]) is not None
    assert claim["claim"] is not None
    assert dependencies == [
        {
            "dependency_id": dependencies[0]["dependency_id"],
            "branch": "main",
            "task_id": task["task_id"],
            "work_item_id": dependent["work_item_id"],
            "depends_on_work_item_id": prereq["work_item_id"],
            "created_at": dependencies[0]["created_at"],
        }
    ]
    assert explanation is not None
    assert explanation["readiness"]["status"] == "blocked"
    assert coordination["task"] is not None
    assert coordination["task"]["task_id"] == task["task_id"]
    assert coordination["work_item"] is not None
    assert coordination["work_item"]["work_item_id"] == prereq["work_item_id"]


def test_proposal_and_index_stores_round_trip_runtime_merge_and_search(memory_project) -> None:
    store = MemoryStore(memory_project.project_path)

    task = store.create_task(
        branch="main",
        title="Ship auth update",
        summary=None,
        acceptance_note=None,
    )
    work_item = store.create_work_item(
        branch="main",
        task_id=task["task_id"],
        title="Implement token refresh",
        work_item_type="implementation",
        subagent_id="builder",
        step_id="step-02-token-refresh",
        scope_descriptor={"paths": ["src/token_refresh.py"]},
    )
    proposal = {
        "proposal_id": "proposal-1",
        "branch": "main",
        "task_id": task["task_id"],
        "work_item_id": work_item["work_item_id"],
        "proposal_type": "patch",
        "status": "pending",
        "session_key": "builder-session",
        "subagent_id": "builder",
        "owner_id": "builder:builder-session",
        "base_revision": 2,
        "target_scope": {"paths": ["src/token_refresh.py"]},
        "payload": {"summary": "Refresh token retry logic"},
        "conflict_hints": {"paths": ["src/token_refresh.py"]},
        "apply_summary": None,
        "created_at": "2026-03-29T00:02:00+00:00",
        "updated_at": "2026-03-29T00:02:00+00:00",
        "applied_at": None,
        "rejected_at": None,
    }
    merge_proposal = {
        "proposalId": "merge-1",
        "sourceBranch": "feature/auth",
        "targetBranch": "main",
        "baseBranch": "main",
        "status": "pending",
        "createdAt": "2026-03-29T00:03:00+00:00",
        "updatedAt": "2026-03-29T00:03:00+00:00",
    }

    store.upsert_runtime_proposal(proposal)
    store.append_runtime_proposal_event(
        {
            "event_id": "event-1",
            "proposal_id": "proposal-1",
            "branch": "main",
            "task_id": task["task_id"],
            "work_item_id": work_item["work_item_id"],
            "event_type": "proposal.published",
            "summary": "Published patch proposal",
            "payload": {"proposal_type": "patch"},
            "ts": "2026-03-29T00:02:10+00:00",
        }
    )
    store.upsert_merge_proposal(merge_proposal)
    store.append_merge_history(
        {
            "eventId": "merge-event-1",
            "proposalId": "merge-1",
            "sourceBranch": "feature/auth",
            "targetBranch": "main",
            "eventType": "merge.requested",
            "summary": "Requested merge into main",
            "payload": {"proposalId": "merge-1"},
            "ts": "2026-03-29T00:03:10+00:00",
        }
    )
    store.upsert_artifact(
        artifact_id="artifact-1",
        branch="main",
        stage="mvp.implement",
        path="src/token_refresh.py",
        content="token refresh retry overview",
        updated_at="2026-03-29T00:04:00+00:00",
    )
    store.log_retrieval_run(
        branch="main",
        stage="mvp.implement",
        step_id="step-02-token-refresh",
        query="token refresh",
        semantic_enabled=False,
        triggers=["manual"],
        exact_count=1,
        lexical_count=1,
        semantic_count=0,
        merged_count=1,
        provider=None,
        model=None,
        revision=None,
        dimension=None,
        namespace_path=None,
        bootstrap_status="disabled",
        semantic_outcome="skipped",
        error_kind=None,
        error_message=None,
    )

    runtime_summary = store.summarize_runtime_proposals(
        branch="main",
        work_item_id=work_item["work_item_id"],
        session_key="builder-session",
    )
    runtime_events = store.list_runtime_proposal_events(proposal_id="proposal-1")
    merge_history = store.list_merge_history(target_branch="main")
    search_results = store.exact_search(
        "retry overview",
        branch="main",
        stage="mvp.implement",
        step_id=None,
        scope="branch",
        limit=5,
        include_obsolete=False,
        include_conflicted=False,
    )
    retrieval_runs = store.list_retrieval_runs(branch="main")

    assert store.fetch_runtime_proposal("proposal-1") is not None
    assert runtime_summary["pending_count"] == 1
    assert runtime_events[0]["proposal_id"] == "proposal-1"
    assert store.fetch_merge_proposal("merge-1") is not None
    assert merge_history[0]["proposalId"] == "merge-1"
    assert store.fetch_artifact("artifact-1") is not None
    assert search_results
    assert search_results[0]["source_type"] == "artifact"
    assert retrieval_runs[0]["query"] == "token refresh"
