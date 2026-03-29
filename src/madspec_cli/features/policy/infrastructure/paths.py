from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


POLICY_SCHEMA_VERSION = 1
SYSTEM_POLICY_BRANCH = "__system__"
SYSTEM_POLICY_STAGE = "policy"
POLICY_KINDS = {"guideline", "rule"}
POLICY_ENFORCEMENTS = {"advisory", "required"}
POLICY_SOURCES = {"system", "user"}
POLICY_STATUSES = {"active", "deprecated"}
PROPOSAL_ACTIONS = {"set", "deprecate"}
PROPOSAL_STATUSES = {"pending", "applied"}
SUPPORTED_RULE_TYPES = {
    "code_steps_require_required_tdd",
    "non_code_steps_forbid_required_tdd",
    "non_required_tdd_requires_waived_phase",
    "completed_code_steps_require_tdd_evidence",
}
STEP_KINDS = {"code", "non-code"}
POLICY_ID_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class PolicyPaths:
    system_dir: Path
    policy_dir: Path
    state_file: Path
    proposals_file: Path
    history_file: Path
    artifact_file: Path


def get_policy_paths(project_path: Path) -> PolicyPaths:
    system_dir = project_path / ".madspec" / "system"
    policy_dir = system_dir / "policy"
    return PolicyPaths(
        system_dir=system_dir,
        policy_dir=policy_dir,
        state_file=policy_dir / "state.json",
        proposals_file=policy_dir / "proposals.jsonl",
        history_file=policy_dir / "history.jsonl",
        artifact_file=system_dir / "policy.md",
    )


__all__ = [
    "POLICY_ENFORCEMENTS",
    "POLICY_ID_PATTERN",
    "POLICY_KINDS",
    "POLICY_SCHEMA_VERSION",
    "POLICY_SOURCES",
    "POLICY_STATUSES",
    "PROPOSAL_ACTIONS",
    "PROPOSAL_STATUSES",
    "PolicyPaths",
    "STEP_KINDS",
    "SUPPORTED_RULE_TYPES",
    "SYSTEM_POLICY_BRANCH",
    "SYSTEM_POLICY_STAGE",
    "get_policy_paths",
]
