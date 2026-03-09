from __future__ import annotations

import json
from pathlib import Path

from .records import LEARNING_KINDS, SEMANTIC_KINDS, make_record
from .storage import append_jsonl, get_memory_paths, read_jsonl


def promote_validated_records(project_path: Path, branch_name: str) -> dict[str, int]:
    paths = get_memory_paths(project_path, branch_name)
    existing = {
        "fact": {record["id"] for record in read_jsonl(paths.facts)},
        "decision": {record["id"] for record in read_jsonl(paths.decisions)},
        "contract": {record["id"] for record in read_jsonl(paths.contracts)},
    }
    counts = {"fact": 0, "decision": 0, "contract": 0}

    candidate_sources = read_jsonl(paths.decision_log) + read_jsonl(paths.events)
    pending: dict[str, list[dict]] = {"fact": [], "decision": [], "contract": []}
    for record in candidate_sources:
        if record.get("status") != "validated":
            continue
        semantic_kind = record.get("semantic_kind")
        if semantic_kind not in SEMANTIC_KINDS:
            continue
        if record["id"] in existing[semantic_kind]:
            continue
        pending[semantic_kind].append(record)
        existing[semantic_kind].add(record["id"])
        counts[semantic_kind] += 1

    append_jsonl(paths.facts, pending["fact"])
    append_jsonl(paths.decisions, pending["decision"])
    append_jsonl(paths.contracts, pending["contract"])
    return counts


def learn_from_outcomes(project_path: Path, branch_name: str, input_path: Path) -> dict[str, int]:
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    paths = get_memory_paths(project_path, branch_name)
    raw = input_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {"events": 0, "semantic_candidates": 0}

    if raw.startswith("["):
        payload = json.loads(raw)
        items = payload if isinstance(payload, list) else [payload]
    elif "\n" in raw:
        items = [json.loads(line) for line in raw.splitlines() if line.strip()]
    else:
        parsed = json.loads(raw)
        items = parsed if isinstance(parsed, list) else [parsed]

    created_events: list[dict] = []
    created_decisions: list[dict] = []
    semantic_candidates = 0
    existing_events = read_jsonl(paths.events)

    for item in items:
        kind = item.get("kind")
        if kind not in LEARNING_KINDS:
            raise ValueError(f"Unsupported learning kind: {kind}")
        stage = item.get("stage", "review")
        step_id = item.get("step_id")
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Learning input requires a non-empty summary")
        evidence = item.get("evidence", [])
        source = item.get("source", f"memory.learn:{kind}")
        metadata = item.get("metadata", {})
        status = item.get("status", "proposed")
        record = make_record(
            branch_name,
            stage,
            source,
            summary,
            step_id=step_id,
            status=status,
            evidence=evidence,
            scope=item.get("scope", "branch"),
            semantic_kind=item.get("semantic_kind"),
            record_type=kind,
            metadata=metadata,
        )
        created_events.append(record)

        if kind == "successful_workaround":
            created_decisions.append(
                {
                    **record,
                    "record_type": "procedural_hint",
                    "semantic_kind": item.get("semantic_kind", "decision"),
                }
            )
            semantic_candidates += 1
            continue

        duplicate_count = sum(
            1 for existing in existing_events if existing.get("summary") == summary
        )
        if kind == "review_finding" or duplicate_count >= 1:
            created_decisions.append(
                {
                    **record,
                    "record_type": "learning_candidate",
                    "semantic_kind": item.get("semantic_kind", "fact"),
                }
            )
            semantic_candidates += 1

    append_jsonl(paths.events, created_events)
    append_jsonl(paths.decision_log, created_decisions)
    return {"events": len(created_events), "semantic_candidates": semantic_candidates}
