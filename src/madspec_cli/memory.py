from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
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


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect_branch(project_path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        branch = result.stdout.strip()
        if branch:
            return branch
    except (FileNotFoundError, OSError):
        pass

    config_path = project_path / ".madspec" / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            branch = config.get("currentBranch")
            if isinstance(branch, str) and branch:
                return branch
        except json.JSONDecodeError:
            pass

    return "main"


def _default_progress_state() -> dict[str, Any]:
    return {
        "currentImplementStep": None,
        "completedSteps": [],
        "plannedSteps": [],
        "stepStatus": {},
        "planningMetadata": {
            "lastPlannedStep": None,
            "planningPhase": "initial",
            "totalStepsEstimated": None,
            "stepDependencies": {},
            "progressMetrics": {
                "p1Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "overallProgress": 0,
            },
        },
    }


def _default_active_session(branch_name: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "branch": branch_name,
        "active_goal": "",
        "stage": "idle",
        "current_step": None,
        "pending_actions": [],
        "open_questions": [],
        "current_hypotheses": [],
        "last_checkpoint_at": None,
        "updated_at": ts,
    }


def _memory_root(project_path: Path, branch_name: str) -> Path:
    return project_path / ".madspec" / branch_name / "memory"


def get_memory_paths(project_path: Path, branch_name: str) -> dict[str, Path]:
    branch_dir = project_path / ".madspec" / branch_name
    memory_dir = _memory_root(project_path, branch_name)
    return {
        "branch_dir": branch_dir,
        "memory_dir": memory_dir,
        "progress": memory_dir / "progress.json",
        "working_dir": memory_dir / "working",
        "active_session": memory_dir / "working" / "active-session.json",
        "decision_log": memory_dir / "working" / "decision-log.jsonl",
        "episodes_dir": memory_dir / "episodes",
        "events": memory_dir / "episodes" / "events.jsonl",
        "semantic_dir": memory_dir / "semantic",
        "facts": memory_dir / "semantic" / "facts.jsonl",
        "decisions": memory_dir / "semantic" / "decisions.jsonl",
        "contracts": memory_dir / "semantic" / "contracts.jsonl",
    }


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def ensure_procedures_layout(project_path: Path) -> list[Path]:
    procedures_dir = project_path / ".madspec" / "procedures"
    procedures_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for relative_name, content in PROCEDURE_FILES.items():
        path = procedures_dir / relative_name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(path)
    return created


def ensure_memory_layout(project_path: Path, branch_name: str) -> list[Path]:
    paths = get_memory_paths(project_path, branch_name)
    created: list[Path] = []

    paths["branch_dir"].mkdir(parents=True, exist_ok=True)
    paths["working_dir"].mkdir(parents=True, exist_ok=True)
    paths["episodes_dir"].mkdir(parents=True, exist_ok=True)
    paths["semantic_dir"].mkdir(parents=True, exist_ok=True)

    if not paths["progress"].exists():
        write_json(paths["progress"], _default_progress_state())
        created.append(paths["progress"])

    if not paths["active_session"].exists():
        write_json(paths["active_session"], _default_active_session(branch_name))
        created.append(paths["active_session"])

    for key in ("decision_log", "events", "facts", "decisions", "contracts"):
        path = paths[key]
        if not path.exists():
            path.write_text("", encoding="utf-8")
            created.append(path)

    created.extend(ensure_procedures_layout(project_path))
    return created


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
) -> dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "ts": now_iso(),
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


def _validate_record(record: dict[str, Any], *, allow_semantic_kind: bool = True) -> list[str]:
    errors: list[str] = []
    for key in ("id", "ts", "branch", "stage", "status", "source", "summary", "evidence"):
        if key not in record:
            errors.append(f"missing field '{key}'")
    if "status" in record and record["status"] not in MEMORY_STATUSES:
        errors.append(f"invalid status '{record['status']}'")
    if "evidence" in record and not isinstance(record["evidence"], list):
        errors.append("evidence must be a list")
    if "step_id" in record and record["step_id"] is not None and not isinstance(record["step_id"], str):
        errors.append("step_id must be a string or null")
    if "scope" in record and record["scope"] not in {"project", "branch", "step", "feature"}:
        errors.append(f"invalid scope '{record['scope']}'")
    if not allow_semantic_kind and "semantic_kind" in record:
        errors.append("semantic_kind is not allowed in this record set")
    if "semantic_kind" in record and record["semantic_kind"] not in SEMANTIC_KINDS:
        errors.append(f"invalid semantic_kind '{record['semantic_kind']}'")
    return errors


def _validate_progress(progress: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("currentImplementStep", "completedSteps", "plannedSteps", "stepStatus", "planningMetadata"):
        if key not in progress:
            errors.append(f"progress.json missing '{key}'")

    if errors:
        return errors

    completed_steps = progress["completedSteps"]
    planned_steps = progress["plannedSteps"]
    step_status = progress["stepStatus"]
    planning_metadata = progress["planningMetadata"]

    if not isinstance(completed_steps, list) or not all(isinstance(item, str) for item in completed_steps):
        errors.append("completedSteps must be a list of strings")
    if not isinstance(planned_steps, list) or not all(isinstance(item, str) for item in planned_steps):
        errors.append("plannedSteps must be a list of strings")
    if not isinstance(step_status, dict):
        errors.append("stepStatus must be an object")
    if not isinstance(planning_metadata, dict):
        errors.append("planningMetadata must be an object")

    if errors:
        return errors

    current_step = progress["currentImplementStep"]
    if current_step is not None and current_step not in planned_steps:
        errors.append("currentImplementStep must be null or reference a planned step")

    for completed in completed_steps:
        if completed not in planned_steps:
            errors.append(f"completed step '{completed}' is not present in plannedSteps")

    step_dependencies = planning_metadata.get("stepDependencies", {})
    if not isinstance(step_dependencies, dict):
        errors.append("planningMetadata.stepDependencies must be an object")
        step_dependencies = {}

    for step_id, dependencies in step_dependencies.items():
        if step_id not in planned_steps:
            errors.append(f"dependency key '{step_id}' is not present in plannedSteps")
        if not isinstance(dependencies, list):
            errors.append(f"dependencies for '{step_id}' must be a list")
            continue
        for dependency in dependencies:
            if dependency not in planned_steps:
                errors.append(f"dependency '{dependency}' for '{step_id}' is not present in plannedSteps")

    for step_id, status_info in step_status.items():
        if step_id not in planned_steps and step_id not in completed_steps:
            errors.append(f"stepStatus key '{step_id}' is not present in planned/completed steps")
        if not isinstance(status_info, dict):
            errors.append(f"stepStatus['{step_id}'] must be an object")
            continue
        status = status_info.get("status")
        if status not in {"planned", "in_progress", "completed"}:
            errors.append(f"stepStatus['{step_id}'].status must be planned/in_progress/completed")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited or node not in step_dependencies:
            return
        if node in visiting:
            errors.append(f"dependency cycle detected at '{node}'")
            return
        visiting.add(node)
        for child in step_dependencies.get(node, []):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for step_id in step_dependencies:
        visit(step_id)

    return errors


def validate_branch_memory(project_path: Path, branch_name: str) -> list[str]:
    paths = get_memory_paths(project_path, branch_name)
    errors: list[str] = []

    progress = read_json(paths["progress"], None)
    if not isinstance(progress, dict):
        errors.append("progress.json must contain a JSON object")
    else:
        errors.extend(_validate_progress(progress))

    active_session = read_json(paths["active_session"], None)
    if not isinstance(active_session, dict):
        errors.append("active-session.json must contain a JSON object")
    else:
        for key in (
            "branch",
            "active_goal",
            "stage",
            "current_step",
            "pending_actions",
            "open_questions",
            "current_hypotheses",
            "last_checkpoint_at",
            "updated_at",
        ):
            if key not in active_session:
                errors.append(f"active-session.json missing '{key}'")
        if active_session.get("branch") != branch_name:
            errors.append("active-session.json branch does not match target branch")
        for key in ("pending_actions", "open_questions", "current_hypotheses"):
            if key in active_session and not isinstance(active_session[key], list):
                errors.append(f"active-session.json field '{key}' must be a list")

    for key in ("decision_log", "events", "facts", "decisions", "contracts"):
        path = paths[key]
        try:
            records = read_jsonl(path)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name} contains invalid JSONL: {exc}")
            continue
        for index, record in enumerate(records, start=1):
            record_errors = _validate_record(record)
            errors.extend(f"{path.name}:{index}: {item}" for item in record_errors)

    if not errors:
        generated_files = consolidate_branch_memory(project_path, branch_name)
        for generated_file in generated_files:
            if not generated_file.exists():
                errors.append(f"derived artifact was not generated: {generated_file}")

    return errors


def _group_records_by_step(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        step_id = record.get("step_id")
        if not step_id:
            continue
        grouped.setdefault(step_id, []).append(record)
    return grouped


def _format_record_lines(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return ["- Нет релевантных записей"]
    lines = []
    for record in sorted(records, key=lambda item: (item.get("ts", ""), item.get("id", ""))):
        status = record.get("status", "unknown")
        source = record.get("source", "unknown")
        summary = record.get("summary", "")
        lines.append(f"- `{status}` {summary} (source: `{source}`)")
    return lines


def _render_project_context(
    branch_name: str,
    progress: dict[str, Any],
    active_session: dict[str, Any],
    generated_at: str,
) -> str:
    planned_steps = progress.get("plannedSteps", [])
    completed_steps = progress.get("completedSteps", [])
    current_stage = active_session.get("stage", "idle") or "idle"
    current_step = active_session.get("current_step") or progress.get("currentImplementStep") or "N/A"
    lines = [
        f"# Project Context ({branch_name})",
        "",
        "> Generated from structured memory. Do not treat this file as the canonical source of truth.",
        "",
        f"- Last generated: `{generated_at}`",
        f"- Current stage: `{current_stage}`",
        f"- Current step: `{current_step}`",
        f"- Progress: `{len(completed_steps)}/{len(planned_steps)}` completed",
        "",
        "## Planned Steps",
    ]
    lines.extend(
        f"- `{step}`" + (" [completed]" if step in completed_steps else "")
        for step in planned_steps
    )
    if not planned_steps:
        lines.append("- No planned steps yet")
    lines.extend(
        [
            "",
            "## Canonical Memory",
            f"- `.madspec/{branch_name}/memory/progress.json`",
            f"- `.madspec/{branch_name}/memory/working/active-session.json`",
            f"- `.madspec/{branch_name}/memory/working/decision-log.jsonl`",
            f"- `.madspec/{branch_name}/memory/episodes/events.jsonl`",
            f"- `.madspec/{branch_name}/memory/semantic/*.jsonl`",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_planning_cache(
    branch_name: str,
    progress: dict[str, Any],
    facts: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    generated_at: str,
) -> str:
    lines = [
        f"# Planning Context Cache ({branch_name})",
        "",
        "> Generated from semantic memory and workflow state.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Progress Metrics",
    ]
    metrics = progress.get("planningMetadata", {}).get("progressMetrics", {})
    for key in ("p1Coverage", "p2Coverage", "p3Coverage"):
        metric = metrics.get(key, {"covered": 0, "total": 0, "percentage": 0})
        lines.append(
            f"- `{key}`: {metric.get('covered', 0)}/{metric.get('total', 0)} ({metric.get('percentage', 0)}%)"
        )
    lines.append(f"- `overallProgress`: {metrics.get('overallProgress', 0)}%")
    lines.extend(["", "## Semantic Facts"])
    lines.extend(_format_record_lines(facts))
    lines.extend(["", "## Validated Decisions"])
    lines.extend(_format_record_lines(decisions))
    lines.extend(["", "## Contracts"])
    lines.extend(_format_record_lines(contracts))
    return "\n".join(lines) + "\n"


def _render_step_context(step_id: str, title: str, records: list[dict[str, Any]], generated_at: str) -> str:
    lines = [
        f"# {title}: {step_id}",
        "",
        "> Generated from structured memory records.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Records",
    ]
    lines.extend(_format_record_lines(records))
    return "\n".join(lines) + "\n"


def _render_review_artifacts(
    review_records: list[dict[str, Any]],
    improvement_records: list[dict[str, Any]],
    generated_at: str,
) -> tuple[str, str]:
    review_lines = [
        "# Review",
        "",
        "> Generated from review-stage structured memory.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Findings",
    ]
    review_lines.extend(_format_record_lines(review_records))

    improvement_lines = [
        "# Improvements",
        "",
        "> Generated from structured memory. Use semantic memory as source of truth.",
        "",
        f"- Last generated: `{generated_at}`",
        "",
        "## Candidate Improvements",
    ]
    improvement_lines.extend(_format_record_lines(improvement_records))
    return "\n".join(review_lines) + "\n", "\n".join(improvement_lines) + "\n"


def consolidate_branch_memory(project_path: Path, branch_name: str) -> list[Path]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths["progress"], _default_progress_state())
    active_session = read_json(paths["active_session"], _default_active_session(branch_name))
    generated_at = active_session.get("updated_at") or active_session.get("last_checkpoint_at") or now_iso()
    decision_log = read_jsonl(paths["decision_log"])
    events = read_jsonl(paths["events"])
    facts = [record for record in read_jsonl(paths["facts"]) if record.get("status") == "validated"]
    decisions = [record for record in read_jsonl(paths["decisions"]) if record.get("status") == "validated"]
    contracts = [record for record in read_jsonl(paths["contracts"]) if record.get("status") == "validated"]

    generated: list[Path] = []

    project_context_path = paths["branch_dir"] / "project-context.md"
    project_context_path.write_text(
        _render_project_context(branch_name, progress, active_session, generated_at),
        encoding="utf-8",
    )
    generated.append(project_context_path)

    planning_cache_path = paths["branch_dir"] / "planning-context-cache.md"
    planning_cache_path.write_text(
        _render_planning_cache(branch_name, progress, facts, decisions, contracts, generated_at),
        encoding="utf-8",
    )
    generated.append(planning_cache_path)

    all_records = decision_log + events + facts + decisions + contracts
    grouped_records = _group_records_by_step(all_records)
    for step_id, step_records in sorted(grouped_records.items()):
        step_dir = paths["branch_dir"] / "steps" / step_id
        if not step_dir.exists():
            continue
        planning_records = [
            record for record in step_records if "plan" in str(record.get("stage", "")).lower()
        ]
        implementation_records = [
            record for record in step_records if "implement" in str(record.get("stage", "")).lower()
        ]
        planning_path = step_dir / "planning-context.md"
        planning_path.write_text(
            _render_step_context(step_id, "Planning Context", planning_records, generated_at),
            encoding="utf-8",
        )
        implementation_path = step_dir / "implementation-context.md"
        implementation_path.write_text(
            _render_step_context(step_id, "Implementation Context", implementation_records, generated_at),
            encoding="utf-8",
        )
        generated.extend([planning_path, implementation_path])

    review_records = [record for record in all_records if record.get("stage") == "review"]
    improvement_records = [
        record
        for record in review_records
        if record.get("record_type") in {"improvement", "review_finding", "question"}
    ]
    review_text, improvements_text = _render_review_artifacts(
        review_records,
        improvement_records,
        generated_at,
    )
    review_path = paths["branch_dir"] / "review.md"
    review_path.write_text(review_text, encoding="utf-8")
    improvements_path = paths["branch_dir"] / "improvements.md"
    improvements_path.write_text(improvements_text, encoding="utf-8")
    generated.extend([review_path, improvements_path])

    return generated


def _filtered_semantic_records(
    path: Path,
    *,
    include_obsolete: bool,
    include_conflicted: bool,
) -> list[dict[str, Any]]:
    records = read_jsonl(path)
    filtered: list[dict[str, Any]] = []
    for record in records:
        status = record.get("status")
        if status == "obsolete" and not include_obsolete:
            continue
        if status == "conflicted" and not include_conflicted:
            continue
        if status == "validated" or include_conflicted or include_obsolete:
            filtered.append(record)
    return filtered


def retrieve_memory_context(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    step_id: str | None = None,
    limit: int = 5,
    include_obsolete: bool = False,
    include_conflicted: bool = False,
) -> dict[str, Any]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths["progress"], _default_progress_state())
    active_session = read_json(paths["active_session"], _default_active_session(branch_name))
    events = read_jsonl(paths["events"])
    decision_log = read_jsonl(paths["decision_log"])

    semantic_facts = _filtered_semantic_records(
        paths["facts"],
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
    )
    semantic_decisions = _filtered_semantic_records(
        paths["decisions"],
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
    )
    semantic_contracts = _filtered_semantic_records(
        paths["contracts"],
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
    )

    stage_lower = stage.lower()
    scoped_events = [
        record
        for record in events
        if (not step_id or record.get("step_id") == step_id)
        and stage_lower in str(record.get("stage", "")).lower()
    ]
    scoped_decisions = [
        record
        for record in decision_log
        if (not step_id or record.get("step_id") == step_id)
        and stage_lower in str(record.get("stage", "")).lower()
    ]

    if "plan" in stage_lower:
        relevant_facts = semantic_facts
        relevant_decisions = [record for record in semantic_decisions if "plan" in record.get("stage", "") or record.get("scope") == "project"]
        relevant_contracts = semantic_contracts
    elif "implement" in stage_lower:
        relevant_facts = [record for record in semantic_facts if record.get("scope") in {"project", "branch", "step"}]
        relevant_decisions = [record for record in semantic_decisions if "implement" in record.get("stage", "") or record.get("step_id") == step_id]
        relevant_contracts = semantic_contracts
    elif "review" in stage_lower:
        relevant_facts = semantic_facts
        relevant_decisions = semantic_decisions
        relevant_contracts = semantic_contracts
    else:
        relevant_facts = semantic_facts
        relevant_decisions = semantic_decisions
        relevant_contracts = semantic_contracts

    def _trim(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(records, key=lambda item: (item.get("ts", ""), item.get("id", "")), reverse=True)[:limit]

    return {
        "branch": branch_name,
        "stage": stage,
        "step_id": step_id,
        "active_session": {
            "active_goal": active_session.get("active_goal"),
            "stage": active_session.get("stage"),
            "current_step": active_session.get("current_step"),
            "open_questions": active_session.get("open_questions", [])[:limit],
            "current_hypotheses": active_session.get("current_hypotheses", [])[:limit],
        },
        "workflow": {
            "currentImplementStep": progress.get("currentImplementStep"),
            "plannedSteps": progress.get("plannedSteps", [])[:limit],
            "completedSteps": progress.get("completedSteps", [])[:limit],
            "stepDependencies": progress.get("planningMetadata", {}).get("stepDependencies", {}),
        },
        "semantic": {
            "facts": _trim(relevant_facts),
            "decisions": _trim(relevant_decisions),
            "contracts": _trim(relevant_contracts),
        },
        "episodes": _trim(scoped_events),
        "decision_log": _trim(scoped_decisions),
    }


def determine_next_step(
    project_path: Path,
    branch_name: str,
    stage: str,
    *,
    candidate_step: str | None = None,
    candidate_dependencies: list[str] | None = None,
    allow_completed_dependencies: bool = True,
) -> dict[str, Any]:
    paths = get_memory_paths(project_path, branch_name)
    progress = read_json(paths["progress"], _default_progress_state())
    planned_steps = progress.get("plannedSteps", [])
    completed_steps = set(progress.get("completedSteps", []))
    step_status = progress.get("stepStatus", {})
    step_dependencies = progress.get("planningMetadata", {}).get("stepDependencies", {})
    stage_lower = stage.lower()

    def _step_ready(step_id: str) -> bool:
        dependencies = step_dependencies.get(step_id, [])
        return all(dependency in completed_steps for dependency in dependencies)

    if candidate_step:
        errors: list[str] = []
        normalized_dependencies = candidate_dependencies or []
        if not STEP_ID_PATTERN.match(candidate_step):
            errors.append("candidate step id must match step-XX-kebab-case")
        if candidate_step in planned_steps:
            errors.append("candidate step id already exists in plannedSteps")
        if len(set(normalized_dependencies)) != len(normalized_dependencies):
            errors.append("candidate dependencies must be unique")
        for dependency in normalized_dependencies:
            if dependency not in planned_steps:
                errors.append(f"dependency '{dependency}' is not present in plannedSteps")
            elif not allow_completed_dependencies and dependency in completed_steps:
                errors.append(f"dependency '{dependency}' is already completed and not allowed by current policy")
        if candidate_step in normalized_dependencies:
            errors.append("candidate step cannot depend on itself")

        decision = {
            "branch": branch_name,
            "stage": stage,
            "candidate_step": candidate_step,
            "dependencies": normalized_dependencies,
            "accepted": not errors,
            "errors": errors,
            "reason": "validated candidate" if not errors else "candidate rejected",
        }
        return decision

    executable_steps = []
    for step_id in planned_steps:
        status = step_status.get(step_id, {}).get("status")
        if step_id in completed_steps or status == "completed":
            continue
        if _step_ready(step_id):
            executable_steps.append(step_id)

    selected_step = executable_steps[0] if executable_steps else None
    if "plan" in stage_lower:
        reason = "next executable planned step for reference" if selected_step else "no executable planned step found"
    else:
        reason = "next executable implementation step" if selected_step else "no executable implementation step found"

    return {
        "branch": branch_name,
        "stage": stage,
        "candidate_step": None,
        "dependencies": step_dependencies.get(selected_step, []) if selected_step else [],
        "accepted": selected_step is not None,
        "selected_step": selected_step,
        "errors": [] if selected_step else ["no executable step available"],
        "reason": reason,
        "executable_steps": executable_steps,
    }


def promote_validated_records(project_path: Path, branch_name: str) -> dict[str, int]:
    paths = get_memory_paths(project_path, branch_name)
    existing = {
        "fact": {record["id"] for record in read_jsonl(paths["facts"])},
        "decision": {record["id"] for record in read_jsonl(paths["decisions"])},
        "contract": {record["id"] for record in read_jsonl(paths["contracts"])},
    }
    counts = {"fact": 0, "decision": 0, "contract": 0}

    candidate_sources = read_jsonl(paths["decision_log"]) + read_jsonl(paths["events"])
    pending: dict[str, list[dict[str, Any]]] = {"fact": [], "decision": [], "contract": []}
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

    append_jsonl(paths["facts"], pending["fact"])
    append_jsonl(paths["decisions"], pending["decision"])
    append_jsonl(paths["contracts"], pending["contract"])
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

    created_events: list[dict[str, Any]] = []
    created_decisions: list[dict[str, Any]] = []
    semantic_candidates = 0
    existing_events = read_jsonl(paths["events"])

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

        duplicate_count = sum(1 for existing in existing_events if existing.get("summary") == summary)
        if kind == "review_finding" or duplicate_count >= 1:
            created_decisions.append(
                {
                    **record,
                    "record_type": "learning_candidate",
                    "semantic_kind": item.get("semantic_kind", "fact"),
                }
            )
            semantic_candidates += 1

    append_jsonl(paths["events"], created_events)
    append_jsonl(paths["decision_log"], created_decisions)
    return {"events": len(created_events), "semantic_candidates": semantic_candidates}
