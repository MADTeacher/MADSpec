from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .storage import get_memory_paths
from .system_store.canonical_state import load_canonical_branch_state
from ..stages.concept.state import is_empty_concept_state, load_concept_state, migrate_legacy_concept_markdown
from ..stages.feature_init.state import (
    is_empty_feature_init_state,
    load_feature_init_state,
    migrate_legacy_project_analysis_markdown,
)


def _normalize_function_label(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    while normalized.startswith("**") and normalized.endswith("**") and len(normalized) >= 4:
        normalized = normalized[2:-2].strip()
    return normalized


def extract_function_catalog(project_path: Path, branch_name: str, stage: str) -> dict[str, list[str]]:
    paths = get_memory_paths(project_path, branch_name)
    stage_lower = stage.lower()
    canonical = load_canonical_branch_state(project_path, branch_name)
    if "feature." in stage_lower:
        feature_init_state = canonical.snapshots.get("feature.init") or load_feature_init_state(paths.feature_init_state)
        legacy_feature_path = paths.branch_dir / "project-analysis.md"
        if is_empty_feature_init_state(feature_init_state) and legacy_feature_path.exists():
            feature_init_state = migrate_legacy_project_analysis_markdown(legacy_feature_path)
        return {
            priority: [
                item.get("id", "")
                for item in feature_init_state.get("features", {}).get(priority, [])
                if item.get("id", "")
            ]
            for priority in ("p1", "p2", "p3")
        }
    concept_state = canonical.snapshots.get("mvp.concept") or load_concept_state(paths.concept_state)
    legacy_concept_path = paths.branch_dir / "concept.md"
    if is_empty_concept_state(concept_state) and legacy_concept_path.exists():
        concept_state = migrate_legacy_concept_markdown(legacy_concept_path)
    return {
        priority: [
            _normalize_function_label(item.get("name", ""))
            for item in concept_state.get("features", {}).get(priority, [])
            if _normalize_function_label(item.get("name", ""))
        ]
        for priority in ("p1", "p2", "p3")
    }


def _compute_progress_metrics(
    catalog: dict[str, list[str]],
    covers_functions: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    weights = {"p1": 0.5, "p2": 0.3, "p3": 0.2}
    overall = 0.0
    for priority in ("p1", "p2", "p3"):
        total = len(catalog.get(priority, []))
        covered_names: set[str] = set()
        for step_coverage in covers_functions.values():
            if not isinstance(step_coverage, dict):
                continue
            values = step_coverage.get(priority, [])
            if isinstance(values, list):
                covered_names.update(item for item in values if isinstance(item, str))
        covered = len(covered_names.intersection(set(catalog.get(priority, []))))
        percentage = int(round((covered / total) * 100)) if total else 0
        metrics[f"{priority}Coverage"] = {
            "covered": covered,
            "total": total,
            "percentage": percentage,
        }
        overall += percentage * weights[priority]
    metrics["overallProgress"] = int(round(overall))
    return metrics
