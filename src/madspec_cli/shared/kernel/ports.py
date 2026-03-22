"""Protocol contracts for inter-module communication between memory/ and features/.

Defines the function-level contracts that memory/ expects from features/.
These protocols serve as documentation and type-checking boundaries;
runtime injection uses lazy imports with default-None parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

class GateEvaluator(Protocol):
    def __call__(
        self,
        project_path: Path,
        branch_name: str,
        *,
        stage: str | None,
        operation: str | None,
        session_key: str = ...,
        step_id: str | None = ...,
        overrides: dict[str, Any] | None = ...,
        include_ratification: bool = ...,
        record_history: bool = ...,
    ) -> dict[str, Any]: ...


class GateFailureExtractor(Protocol):
    def __call__(self, payload: dict[str, Any]) -> list[str]: ...


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class BranchPolicyEvaluator(Protocol):
    def __call__(
        self,
        project_path: Path,
        branch_name: str,
        *,
        stage: str | None,
        operation: str | None,
        step_id: str | None = ...,
        overrides: dict[str, Any] | None = ...,
        include_system_policies: bool = ...,
        policy_id: str | None = ...,
        create_policy_if_missing: bool = ...,
    ) -> dict[str, Any]: ...


class PolicyContextBuilder(Protocol):
    def __call__(
        self,
        project_path: Path,
        *,
        stage: str | None = ...,
        create_if_missing: bool = ...,
    ) -> dict[str, Any]: ...


class PolicyStateLoader(Protocol):
    def __call__(
        self,
        project_path: Path,
        *,
        create_if_missing: bool = ...,
    ) -> dict[str, Any]: ...


class PolicySummarizer(Protocol):
    def __call__(
        self,
        project_path: Path,
        *,
        stage: str | None = ...,
        create_if_missing: bool = ...,
    ) -> dict[str, Any]: ...


class PolicyLayoutEnsurer(Protocol):
    def __call__(self, project_path: Path) -> list[Path]: ...


# ---------------------------------------------------------------------------
# Change
# ---------------------------------------------------------------------------

class ChangeContextBuilder(Protocol):
    def __call__(
        self,
        project_path: Path,
        branch_name: str,
    ) -> dict[str, Any]: ...


class ChangeStateLoader(Protocol):
    def __call__(
        self,
        project_path: Path,
        branch_name: str,
    ) -> dict[str, Any] | None: ...


class DefaultBaseBranchResolver(Protocol):
    def __call__(self, project_path: Path) -> str: ...


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class AgentsLayoutEnsurer(Protocol):
    def __call__(
        self,
        project_path: Path,
        *,
        environment_id: str | None = ...,
    ) -> tuple[dict[str, Any], list[Path]]: ...


class SubagentFinder(Protocol):
    def __call__(
        self,
        project_path: Path,
        subagent_id: str,
    ) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

class CurrentBranchResolver(Protocol):
    def __call__(self, project_path: Path) -> str: ...
