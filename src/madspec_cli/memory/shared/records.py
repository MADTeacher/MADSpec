from __future__ import annotations

import re
import uuid
from typing import Any

MEMORY_STATUSES = {"proposed", "validated", "obsolete", "conflicted"}
SEMANTIC_KINDS = {"fact", "decision", "contract"}
LEARNING_KINDS = {"test_failure", "review_finding", "successful_workaround"}
STEP_ID_PATTERN = re.compile(r"^step-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")

PROCEDURE_FILES = {
    "next-step-selection.md": """# Next Step Selection

1. Read `memory/progress.json`.
2. Read retrieved semantic constraints for the target stage.
3. For planning, validate candidate step id, dependencies, and duplicate names with `madspec memory next-step`.
4. For implementation, use `madspec memory next-step` to select the next executable planned step.
5. Persist the accepted decision in `memory/working/decision-log.jsonl`.
""",
    "validation-checks.md": """# Validation Checks

- Validate JSON/JSONL schemas before and after each checkpoint.
- Reject illegal `progress.json` transitions.
- Reject broken step references or dependency cycles.
- Run `madspec memory consolidate` and `madspec memory validate`.
""",
    "promotion-guardrails.md": """# Promotion Guardrails

- Promote only `validated` records.
- Never promote `obsolete` or `conflicted` records by default.
- Semantic knowledge must include `summary`, `source`, and `evidence`.
""",
    "learning-rules.md": """# Learning Rules

- Failed test -> episodic event.
- Repeated failure pattern -> semantic constraint candidate.
- Review finding -> improvement candidate and open question.
- Successful workaround -> procedural hint.
""",
}


def make_record(
    branch_name: str,
    stage: str,
    source: str,
    summary: str,
    *,
    step_id: str | None = None,
    status: str = "proposed",
    evidence: list[str] | None = None,
    scope: str = "branch",
    semantic_kind: str | None = None,
    record_type: str = "event",
    metadata: dict[str, Any] | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    from .storage import now_iso

    record = {
        "id": str(uuid.uuid4()),
        "ts": ts or now_iso(),
        "branch": branch_name,
        "stage": stage,
        "step_id": step_id,
        "status": status,
        "source": source,
        "summary": summary,
        "evidence": evidence or [],
        "scope": scope,
        "record_type": record_type,
    }
    if semantic_kind:
        record["semantic_kind"] = semantic_kind
    if metadata:
        record["metadata"] = metadata
    return record
