from __future__ import annotations


def resolve_target_branch(branch_name: str | None, *, fallback_branch: str) -> str:
    return branch_name or fallback_branch
