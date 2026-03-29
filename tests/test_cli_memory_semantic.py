from __future__ import annotations

import json

from madspec_cli.memory import get_memory_paths
from madspec_cli.memory.domain.conflicts import PROJECT_MEMORY_BRANCH, semantic_fingerprint
from madspec_cli.memory.shared.records import make_record
from madspec_cli.memory.shared.storage import ensure_memory_layout
from madspec_cli.memory.shared.system_store import refresh_branch_projections
from madspec_cli.memory.shared.system_store.store import MemoryStore

from tests.test_cli_memory_proposals import _create_claim, _setup_claimed_work_item


def test_memory_semantic_retrieve_branch_returns_full_artifact_and_revision(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    seeded = _seed_branch_semantic(project_path, "main")

    result = invoke_cli(
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

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["scope"] == "branch"
    assert payload["branch"] == "main"
    assert payload["runtime_revision"] >= 0
    assert payload["counts"] == {"facts": 2, "decisions": 1, "contracts": 1}
    fact_ids = {item["id"] for item in payload["semantic"]["facts"]}
    assert seeded["facts"][0]["id"] in fact_ids
    assert all(item["fingerprint"] for item in payload["semantic"]["facts"])


def test_memory_semantic_prune_branch_from_tmp_file_cleans_args_and_active_index(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    seeded = _seed_branch_semantic(project_path, "main")
    store = MemoryStore(project_path)
    store.process_pending_jobs(rebuild=True, limit=500)
    before_index = store.describe_record_index(seeded["facts"][1]["id"])
    assert before_index["memory_chunk_count"] > 0

    tmp_dir = project_path / ".madspec" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    args_file = tmp_dir / "semantic-prune.json"
    args_file.write_text(
        json.dumps(
            {
                "scope": "branch",
                "branch": "main",
                "summary": "Prune duplicate semantic facts",
                "operations": [
                    {
                        "semantic_kind": "fact",
                        "record_id": seeded["facts"][1]["id"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = invoke_cli(
        [
            "memory",
            "semantic",
            "prune",
            "--from-file",
            ".madspec/.tmp/semantic-prune.json",
            "--json-output",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True
    assert payload["details"]["removed_count"] == 1
    assert not args_file.exists()

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

    after_index = store.describe_record_index(seeded["facts"][1]["id"])
    assert after_index["memory_chunk_count"] == 0

    paths = get_memory_paths(project_path, "main")
    facts_projection = paths.facts.read_text(encoding="utf-8")
    assert seeded["facts"][1]["id"] not in facts_projection


def test_memory_semantic_replace_branch_rewrites_semantic_projection(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    seeded = _seed_branch_semantic(project_path, "main")

    replace_payload = {
        "scope": "branch",
        "branch": "main",
        "summary": "Replace semantic knowledge with canonical copy",
        "semantic": {
            "facts": [seeded["facts"][0]],
            "decisions": seeded["decisions"],
            "contracts": [],
        },
    }
    args_file = project_path / ".madspec" / ".tmp" / "semantic-replace.json"
    args_file.parent.mkdir(parents=True, exist_ok=True)
    args_file.write_text(json.dumps(replace_payload), encoding="utf-8")

    result = invoke_cli(
        [
            "memory",
            "semantic",
            "replace",
            "--from-file",
            ".madspec/.tmp/semantic-replace.json",
            "--json-output",
        ]
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["accepted"] is True

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
    assert retrieve_payload["counts"] == {"facts": 1, "decisions": 1, "contracts": 0}

    paths = get_memory_paths(project_path, "main")
    contracts_projection = paths.contracts.read_text(encoding="utf-8")
    assert contracts_projection == ""


def test_memory_semantic_project_scope_prune_removes_promoted_record_and_search_scope_project_stays_clean(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    seeded = _seed_branch_semantic(project_path, "main")

    promote_result = invoke_cli(
        [
            "memory",
            "promote-branch-knowledge",
            "--source-branch",
            "main",
            "--json-output",
        ]
    )
    assert promote_result.exit_code == 0, promote_result.stdout

    store = MemoryStore(project_path)
    store.process_pending_jobs(rebuild=True, limit=500)

    project_retrieve = invoke_cli(
        [
            "memory",
            "semantic",
            "retrieve",
            "--scope",
            "project",
            "--json-output",
        ]
    )
    assert project_retrieve.exit_code == 0, project_retrieve.stdout
    project_payload = json.loads(project_retrieve.stdout)
    assert project_payload["scope"] == "project"
    assert project_payload["branch"] is None
    assert project_payload["counts"]["decisions"] >= 1

    target_record = next(
        item
        for item in project_payload["semantic"]["decisions"]
        if item["summary"] == seeded["decisions"][0]["summary"]
    )
    target_fingerprint = target_record["fingerprint"]

    args_file = project_path / ".madspec" / ".tmp" / "project-semantic-prune.json"
    args_file.parent.mkdir(parents=True, exist_ok=True)
    args_file.write_text(
        json.dumps(
            {
                "scope": "project",
                "summary": "Prune promoted project fact",
                    "operations": [
                        {
                            "semantic_kind": "decision",
                            "fingerprint": target_fingerprint,
                        }
                    ],
            }
        ),
        encoding="utf-8",
    )

    prune_result = invoke_cli(
        [
            "memory",
            "semantic",
            "prune",
            "--from-file",
            ".madspec/.tmp/project-semantic-prune.json",
            "--json-output",
        ]
    )
    assert prune_result.exit_code == 0, prune_result.stdout
    prune_payload = json.loads(prune_result.stdout)
    assert prune_payload["accepted"] is True
    assert prune_payload["projection_status"] == "not_applicable"
    assert prune_payload["generated_views"] == []

    project_after = invoke_cli(
        [
            "memory",
            "semantic",
            "retrieve",
            "--scope",
            "project",
            "--json-output",
        ]
    )
    assert project_after.exit_code == 0, project_after.stdout
    after_payload = json.loads(project_after.stdout)
    decision_ids = {item["id"] for item in after_payload["semantic"]["decisions"]}
    assert target_record["id"] not in decision_ids

    search_result = invoke_cli(
        [
            "memory",
            "search",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--scope",
            "project",
            "--query",
            seeded["decisions"][0]["summary"],
            "--json-output",
        ]
    )
    assert search_result.exit_code == 0, search_result.stdout
    search_payload = json.loads(search_result.stdout)
    assert all(
        not (
            item["summary"] == seeded["decisions"][0]["summary"]
            and item.get("branch") == "__project__"
        )
        for item in search_payload["merged"]
    )

    project_index = store.describe_record_index(target_record["id"])
    assert project_index["memory_chunk_count"] == 0


def test_memory_semantic_retrieve_can_include_obsolete_and_conflicted_records(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    _seed_branch_semantic(project_path, "main")
    store = MemoryStore(project_path)
    obsolete_fact = _semantic_record(
        "main",
        "mvp.plan",
        "fact",
        "Deprecated matchmaking note",
        source="memory.promote",
        metadata={"topic": "deprecated"},
        status="obsolete",
    )
    conflicted_decision = _semantic_record(
        "main",
        "mvp.plan",
        "decision",
        "Conflicted prize policy",
        source="memory.promote",
        metadata={"topic": "conflict"},
        status="conflicted",
    )
    store.upsert_records_batch([obsolete_fact, conflicted_decision])
    refresh_branch_projections(project_path, "main", full=True)

    default_result = invoke_cli(
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
    assert default_result.exit_code == 0, default_result.stdout
    default_payload = json.loads(default_result.stdout)
    summaries = {item["summary"] for item in default_payload["semantic"]["facts"]}
    assert "Deprecated matchmaking note" not in summaries

    expanded_result = invoke_cli(
        [
            "memory",
            "semantic",
            "retrieve",
            "--scope",
            "branch",
            "--branch",
            "main",
            "--include-obsolete",
            "--include-conflicted",
            "--json-output",
        ]
    )
    assert expanded_result.exit_code == 0, expanded_result.stdout
    expanded_payload = json.loads(expanded_result.stdout)
    fact_records = {item["summary"]: item for item in expanded_payload["semantic"]["facts"]}
    decision_records = {item["summary"]: item for item in expanded_payload["semantic"]["decisions"]}
    assert fact_records["Deprecated matchmaking note"]["status"] == "obsolete"
    assert decision_records["Conflicted prize policy"]["status"] == "conflicted"


def test_memory_semantic_prune_can_remove_obsolete_and_conflicted_records(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    _seed_branch_semantic(project_path, "main")
    store = MemoryStore(project_path)
    obsolete_fact = _semantic_record(
        "main",
        "mvp.plan",
        "fact",
        "Temporary obsolete fact",
        source="memory.promote",
        metadata={"topic": "obsolete"},
        status="obsolete",
    )
    conflicted_decision = _semantic_record(
        "main",
        "mvp.plan",
        "decision",
        "Temporary conflicted decision",
        source="memory.promote",
        metadata={"topic": "conflicted"},
        status="conflicted",
    )
    store.upsert_records_batch([obsolete_fact, conflicted_decision])
    refresh_branch_projections(project_path, "main", full=True)

    args_file = project_path / ".madspec" / ".tmp" / "semantic-prune-statuses.json"
    args_file.parent.mkdir(parents=True, exist_ok=True)
    args_file.write_text(
        json.dumps(
            {
                "scope": "branch",
                "branch": "main",
                "operations": [
                    {
                        "semantic_kind": "fact",
                        "record_id": obsolete_fact["id"],
                    },
                    {
                        "semantic_kind": "decision",
                        "fingerprint": semantic_fingerprint(conflicted_decision),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    prune_result = invoke_cli(
        [
            "memory",
            "semantic",
            "prune",
            "--from-file",
            ".madspec/.tmp/semantic-prune-statuses.json",
            "--json-output",
        ]
    )
    assert prune_result.exit_code == 0, prune_result.stdout
    prune_payload = json.loads(prune_result.stdout)
    assert prune_payload["accepted"] is True
    assert prune_payload["details"]["removed_count"] == 2

    after_result = invoke_cli(
        [
            "memory",
            "semantic",
            "retrieve",
            "--scope",
            "branch",
            "--branch",
            "main",
            "--include-obsolete",
            "--include-conflicted",
            "--json-output",
        ]
    )
    assert after_result.exit_code == 0, after_result.stdout
    after_payload = json.loads(after_result.stdout)
    fact_summaries = {item["summary"] for item in after_payload["semantic"]["facts"]}
    decision_summaries = {item["summary"] for item in after_payload["semantic"]["decisions"]}
    assert "Temporary obsolete fact" not in fact_summaries
    assert "Temporary conflicted decision" not in decision_summaries


def test_memory_project_scope_is_strict_for_retrieve_and_search(
    make_madspec_project,
    invoke_cli,
) -> None:
    project_path = make_madspec_project()
    _seed_branch_semantic(project_path, "main")

    promote_result = invoke_cli(
        [
            "memory",
            "promote-branch-knowledge",
            "--source-branch",
            "main",
            "--json-output",
        ]
    )
    assert promote_result.exit_code == 0, promote_result.stdout

    branch_only_fact = _semantic_record(
        "main",
        "mvp.plan",
        "fact",
        "Branch-only runtime fact",
        source="memory.promote",
        metadata={"topic": "branch-only"},
    )
    store = MemoryStore(project_path)
    store.upsert_records_batch([branch_only_fact])
    refresh_branch_projections(project_path, "main", full=True)
    store.process_pending_jobs(rebuild=True, limit=500)

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--scope",
            "project",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    fact_summaries = {item["summary"] for item in retrieve_payload["semantic"]["facts"]}
    assert "Branch-only runtime fact" not in fact_summaries

    search_result = invoke_cli(
        [
            "memory",
            "search",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--scope",
            "project",
            "--query",
            "Branch-only runtime fact",
            "--json-output",
        ]
    )
    assert search_result.exit_code == 0, search_result.stdout
    search_payload = json.loads(search_result.stdout)
    assert search_payload["runtime_revision"] == MemoryStore(project_path).fetch_branch_revision(PROJECT_MEMORY_BRANCH)
    assert all(item["branch"] == PROJECT_MEMORY_BRANCH for item in search_payload["merged"])
    assert all(item["summary"] != "Branch-only runtime fact" for item in search_payload["merged"])


def test_memory_semantic_from_file_rejects_unknown_fields_and_claimed_branch_session_auto_publishes_and_applies_proposal(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    _seed_branch_semantic(project_path, "main")
    _create_claim(
        invoke_cli,
        task_title="Coordinate semantic cleanup",
        work_title="Cleanup semantic branch knowledge",
        subagent_id="developer",
        session_key="cleanup",
        step_id=None,
        path="semantic/facts.jsonl",
    )

    bad_args = project_path / ".madspec" / ".tmp" / "bad-semantic.json"
    bad_args.parent.mkdir(parents=True, exist_ok=True)
    bad_args.write_text(
        json.dumps(
            {
                "scope": "branch",
                "branch": "main",
                "operations": [],
                "mystery_field": "??",
            }
        ),
        encoding="utf-8",
    )
    bad_result = invoke_cli(
        [
            "memory",
            "semantic",
            "prune",
            "--from-file",
            ".madspec/.tmp/bad-semantic.json",
        ]
    )
    assert bad_result.exit_code != 0
    assert "Unsupported fields in args file: mystery_field" in (bad_result.stdout + bad_result.stderr)
    assert bad_args.exists()

    claimed_args = project_path / ".madspec" / ".tmp" / "claimed-semantic.json"
    claimed_args.write_text(
        json.dumps(
            {
                "scope": "branch",
                "branch": "main",
                "session_key": "cleanup",
                "operations": [
                    {
                        "semantic_kind": "fact",
                        "match": {"summary": "Keep current leaderboard snapshot for replay"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    claimed_result = invoke_cli(
        [
            "memory",
            "semantic",
            "prune",
            "--from-file",
            ".madspec/.tmp/claimed-semantic.json",
            "--json-output",
        ]
    )
    assert claimed_result.exit_code == 0, claimed_result.stdout
    claimed_payload = json.loads(claimed_result.stdout)
    assert claimed_payload["accepted"] is True
    assert claimed_payload["proposal_mode"] is True
    assert claimed_payload["apply_required"] is True
    assert claimed_payload["proposal"]["proposal_type"] == "semantic_cleanup"
    proposal_id = claimed_payload["proposal"]["proposal_id"]
    assert not claimed_args.exists()

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
    assert preview_payload["proposal"]["proposal_type"] == "semantic_cleanup"
    assert preview_payload["proposal"]["status"] == "pending"

    list_result = invoke_cli(
        [
            "memory",
            "proposals",
            "list",
            "--branch",
            "main",
            "--session-key",
            "cleanup",
            "--json-output",
        ]
    )
    assert list_result.exit_code == 0, list_result.stdout
    list_payload = json.loads(list_result.stdout)
    assert any(item["proposal_id"] == proposal_id for item in list_payload["proposals"])

    explain_result = invoke_cli(
        [
            "memory",
            "explain",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--session-key",
            "cleanup",
            "--json-output",
        ]
    )
    assert explain_result.exit_code == 0, explain_result.stdout
    explain_payload = json.loads(explain_result.stdout)
    assert explain_payload["observability"]["proposal_state"]["latest"]["proposal_type"] == "semantic_cleanup"
    assert explain_payload["observability"]["proposal_state"]["latest"]["status"] == "pending"

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
    fact_summaries = {item["summary"] for item in retrieve_payload["semantic"]["facts"]}
    assert "Keep current leaderboard snapshot for replay" not in fact_summaries


def test_memory_semantic_claimed_branch_proposal_apply_detects_stale_revision(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = _setup_claimed_work_item(tmp_path, monkeypatch, invoke_cli, init_memory_branch)
    seeded = _seed_branch_semantic(project_path, "main")
    _create_claim(
        invoke_cli,
        task_title="Coordinate semantic cleanup",
        work_title="Cleanup semantic branch knowledge",
        subagent_id="developer",
        session_key="cleanup",
        step_id=None,
        path="semantic/facts.jsonl",
    )

    claimed_args = project_path / ".madspec" / ".tmp" / "claimed-semantic-stale.json"
    claimed_args.parent.mkdir(parents=True, exist_ok=True)
    claimed_args.write_text(
        json.dumps(
            {
                "scope": "branch",
                "branch": "main",
                "session_key": "cleanup",
                "operations": [
                    {
                        "semantic_kind": "fact",
                        "record_id": seeded["facts"][1]["id"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    claimed_result = invoke_cli(
        [
            "memory",
            "semantic",
            "prune",
            "--from-file",
            ".madspec/.tmp/claimed-semantic-stale.json",
            "--json-output",
        ]
    )
    assert claimed_result.exit_code == 0, claimed_result.stdout
    proposal_id = json.loads(claimed_result.stdout)["proposal"]["proposal_id"]

    direct_args = project_path / ".madspec" / ".tmp" / "direct-semantic-prune.json"
    direct_args.write_text(
        json.dumps(
            {
                "scope": "branch",
                "branch": "main",
                "operations": [
                    {
                        "semantic_kind": "contract",
                        "record_id": seeded["contracts"][0]["id"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    direct_result = invoke_cli(
        [
            "memory",
            "semantic",
            "prune",
            "--from-file",
            ".madspec/.tmp/direct-semantic-prune.json",
            "--json-output",
        ]
    )
    assert direct_result.exit_code == 0, direct_result.stdout

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
    assert apply_result.exit_code == 1, apply_result.stdout
    apply_payload = json.loads(apply_result.stdout)
    assert apply_payload["proposal"]["status"] == "conflict"
    assert apply_payload["proposal"]["apply_summary"]["reason"] == "stale_revision"


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
    status: str = "validated",
) -> dict[str, object]:
    record = make_record(
        branch_name,
        stage,
        source,
        summary,
        status=status,
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
