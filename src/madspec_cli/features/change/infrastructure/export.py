from __future__ import annotations

import json
from pathlib import Path

from .paths import get_change_paths
from .rendering import (
    render_change_plan_markdown,
    render_change_spec_markdown,
    render_change_summary_markdown,
    render_change_tasks_markdown,
)


def write_change_summary_artifact(project_path: Path, branch_name: str, bundle: dict) -> Path:
    paths = get_change_paths(project_path, branch_name)
    body = render_change_summary_markdown(bundle)
    paths.summary_artifact.write_text(body, encoding="utf-8")
    return paths.summary_artifact


def export_change_bundle(
    project_path: Path,
    branch_name: str,
    bundle: dict,
) -> tuple[Path, list[dict[str, str]]]:
    from madspec_cli.memory.shared.system_store.sync import sync_generated_artifacts
    from .snapshot import _hash_path

    paths = get_change_paths(project_path, branch_name)
    export_dir = paths.export_dir / f"{bundle['bundleId']}-r{bundle['revision']}"
    export_dir.mkdir(parents=True, exist_ok=True)

    bundle_file = export_dir / "bundle.json"
    bundle_file.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary_file = export_dir / "summary.md"
    summary_file.write_text(render_change_summary_markdown(bundle), encoding="utf-8")
    spec_file = export_dir / "spec.md"
    spec_file.write_text(render_change_spec_markdown(project_path, branch_name, bundle), encoding="utf-8")
    plan_file = export_dir / "plan.md"
    plan_file.write_text(render_change_plan_markdown(project_path, branch_name, bundle), encoding="utf-8")
    tasks_file = export_dir / "tasks.md"
    tasks_file.write_text(render_change_tasks_markdown(project_path, branch_name, bundle), encoding="utf-8")

    exported = []
    for path in (bundle_file, summary_file, spec_file, plan_file, tasks_file):
        exported.append(
            {
                "path": str(path.relative_to(project_path)),
                "contentHash": _hash_path(path) or "",
            }
        )
    sync_generated_artifacts(project_path, branch_name)
    return export_dir, exported


__all__ = ["export_change_bundle", "write_change_summary_artifact"]
