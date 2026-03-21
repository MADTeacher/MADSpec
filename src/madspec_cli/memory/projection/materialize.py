from __future__ import annotations

from pathlib import Path

from madspec_cli.features.change.infrastructure.storage import build_change_context
from madspec_cli.memory.shared.system_store.store import MemoryStore

from ..shared.stage_scope import resolve_stage_scope
from ..stages.architecture.state import render_data_model_markdown, render_openapi_yaml
from ..stages.concept.state import render_concept_markdown
from ..stages.design.state import render_ui_design_markdown
from ..stages.feature_plan.state import is_empty_plan_state as is_empty_feature_plan_state
from .context_loader import load_branch_projection_state, load_materialization_records
from .materializers import feature as feature_materializer
from .materializers import mvp as mvp_materializer
from .policy_gate_summary import build_materialization_summaries, build_step_gate_summary
from .projections import group_records_by_step
from .renderers import (
    render_planning_cache,
    render_project_context,
    render_review_artifacts,
    render_security_artifact,
    render_step_context,
)


def _write_generated(
    path: Path,
    content: str,
    generated: list[Path],
    artifacts: list[dict[str, str]],
    *,
    project_path: Path,
    branch_name: str,
    stage: str | None,
    updated_at: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    generated.append(path)
    artifacts.append(
        {
            "artifact_id": str(path.relative_to(project_path)),
            "path": str(path.relative_to(project_path)),
            "content": content,
            "stage": stage or "",
            "updated_at": updated_at,
        }
    )


def consolidate_branch_memory(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None = None,
    full: bool = False,
) -> list[Path]:
    state = load_branch_projection_state(project_path, branch_name)
    records = load_materialization_records(
        state.paths,
        project_path=project_path,
        branch_name=branch_name,
    )
    scope = resolve_stage_scope(stage, full=full)
    generated: list[Path] = []
    artifacts: list[dict[str, str]] = []
    summaries = build_materialization_summaries(
        project_path,
        branch_name,
        active_session=state.active_session,
        progress=state.progress,
        feature_mode=state.feature_mode,
    )

    if "concept" in scope.view_keys:
        _write_generated(
            state.paths.branch_dir / "concept.md",
            render_concept_markdown(state.concept_state),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="mvp.concept",
            updated_at=state.generated_at,
        )

    if "ui-design" in scope.view_keys:
        _write_generated(
            state.paths.branch_dir / "ui-design.md",
            render_ui_design_markdown(
                state.design_state,
                branch_name=branch_name,
                project_name=state.concept_state.get("projectName", ""),
            ),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="mvp.design",
            updated_at=state.generated_at,
        )

    if "tech-stack" in scope.view_keys:
        tech_content = (
            feature_materializer.render_tech_stack(state.feature_init_state, branch_name=branch_name)
            if state.feature_mode
            else mvp_materializer.render_tech_stack(
                state.tech_state,
                branch_name=branch_name,
                project_name=state.concept_state.get("projectName", ""),
            )
        )
        _write_generated(
            state.paths.branch_dir / "tech-stack.md",
            tech_content,
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="mvp.tech" if not state.feature_mode else "feature.init",
            updated_at=state.generated_at,
        )

    if "architecture" in scope.view_keys:
        architecture_content = (
            feature_materializer.render_architecture(state.feature_init_state, branch_name=branch_name)
            if state.feature_mode
            else mvp_materializer.render_architecture(
                state.architecture_state,
                branch_name=branch_name,
                project_name=state.concept_state.get("projectName", ""),
            )
        )
        _write_generated(
            state.paths.branch_dir / "architecture.md",
            architecture_content,
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="mvp.architecture" if not state.feature_mode else "feature.init",
            updated_at=state.generated_at,
        )

    if "project-analysis" in scope.view_keys:
        _write_generated(
            state.paths.branch_dir / "project-analysis.md",
            feature_materializer.render_project_analysis(state.feature_init_state),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="feature.init",
            updated_at=state.generated_at,
        )

    if "feature-context" in scope.view_keys:
        _write_generated(
            state.paths.branch_dir / "feature-context.md",
            feature_materializer.render_feature_context(state.feature_init_state),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="feature.init",
            updated_at=state.generated_at,
        )

    if "data-model" in scope.view_keys:
        _write_generated(
            state.paths.branch_dir / "data-model.md",
            render_data_model_markdown(
                state.architecture_state,
                branch_name=branch_name,
                project_name=state.concept_state.get("projectName", ""),
            ),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="mvp.architecture",
            updated_at=state.generated_at,
        )

    if "openapi" in scope.view_keys:
        _write_generated(
            state.paths.branch_dir / "contracts" / "openapi.yaml",
            render_openapi_yaml(state.architecture_state, branch_name=branch_name),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="mvp.architecture",
            updated_at=state.generated_at,
        )

    if "project-context" in scope.view_keys:
        _write_generated(
            state.paths.branch_dir / "project-context.md",
            render_project_context(
                branch_name,
                state.progress,
                state.active_session,
                state.concept_state,
                state.design_state,
                state.tech_state,
                state.architecture_state,
                state.plan_state,
                state.feature_init_state,
                state.feature_plan_state,
                summaries["policy_summary"],
                state.generated_at,
                current_gate_summary=summaries["current_gate_summary"],
                review_gate_summary=summaries["review_gate_summary"],
                security_gate_summary=summaries["security_gate_summary"],
            ),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="mvp.implement" if not state.feature_mode else "feature.implement",
            updated_at=state.generated_at,
        )

    if "planning-cache" in scope.view_keys:
        _write_generated(
            state.paths.branch_dir / "planning-context-cache.md",
            render_planning_cache(
                branch_name,
                state.progress,
                records.facts,
                records.decisions,
                records.contracts,
                state.generated_at,
            ),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="mvp.plan" if not state.feature_mode else "feature.plan",
            updated_at=state.generated_at,
        )

    if "implementation-plan" in scope.view_keys:
        implementation_content = (
            feature_materializer.render_implementation_plan(
                state.feature_plan_state,
                branch_name=branch_name,
                progress=state.progress,
                feature_goal=state.feature_init_state.get("featureGoal", ""),
            )
            if state.feature_mode and not is_empty_feature_plan_state(state.feature_plan_state)
            else mvp_materializer.render_implementation_plan(
                state.plan_state,
                branch_name=branch_name,
                progress=state.progress,
                project_name=state.concept_state.get("projectName", ""),
            )
        )
        _write_generated(
            state.paths.branch_dir / "implementation-plan.md",
            implementation_content,
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="feature.plan" if state.feature_mode else "mvp.plan",
            updated_at=state.generated_at,
        )

    all_records = records.decision_log + records.events + records.facts + records.decisions + records.contracts
    if scope.full or scope.stage in {"mvp.plan", "feature.plan", "mvp.implement", "feature.implement"}:
        grouped_records = group_records_by_step(all_records)
        step_metadata = state.progress.get("stepMetadata", {})
        step_status = state.progress.get("stepStatus", {})
        for step_id, step_records in sorted(grouped_records.items()):
            step_dir = state.paths.branch_dir / "steps" / step_id
            if not step_dir.exists():
                continue
            planning_records = [record for record in step_records if "plan" in str(record.get("stage", "")).lower()]
            implementation_records = [
                record for record in step_records if "implement" in str(record.get("stage", "")).lower()
            ]
            _write_generated(
                step_dir / "planning-context.md",
                render_step_context(
                    step_id,
                    "Planning Context",
                    planning_records,
                    state.generated_at,
                    step_metadata=step_metadata.get(step_id),
                    status_info=step_status.get(step_id),
                    gate_summary=build_step_gate_summary(
                        project_path,
                        branch_name,
                        stage=summaries["planning_stage"],
                        step_id=step_id,
                    ),
                ),
                generated,
                artifacts,
                project_path=project_path,
                branch_name=branch_name,
                stage=summaries["planning_stage"],
                updated_at=state.generated_at,
            )
            _write_generated(
                step_dir / "implementation-context.md",
                render_step_context(
                    step_id,
                    "Implementation Context",
                    implementation_records,
                    state.generated_at,
                    step_metadata=step_metadata.get(step_id),
                    status_info=step_status.get(step_id),
                    gate_summary=build_step_gate_summary(
                        project_path,
                        branch_name,
                        stage=summaries["implementation_stage"],
                        step_id=step_id,
                    ),
                ),
                generated,
                artifacts,
                project_path=project_path,
                branch_name=branch_name,
                stage=summaries["implementation_stage"],
                updated_at=state.generated_at,
            )

    review_records = [record for record in all_records if record.get("stage") == "review"]
    improvement_records = [
        record
        for record in review_records
        if record.get("record_type") in {"improvement", "review_finding", "question"}
    ]
    change_context = build_change_context(project_path, branch_name)

    if "review" in scope.view_keys or "improvements" in scope.view_keys:
        review_text, improvements_text = render_review_artifacts(
            review_records,
            improvement_records,
            state.generated_at,
            change_context=change_context,
            gate_summary=summaries["review_gate_summary"],
        )
        if "review" in scope.view_keys:
            _write_generated(
                state.paths.branch_dir / "review.md",
                review_text,
                generated,
                artifacts,
                project_path=project_path,
                branch_name=branch_name,
                stage="review",
                updated_at=state.generated_at,
            )
        if "improvements" in scope.view_keys:
            _write_generated(
                state.paths.branch_dir / "improvements.md",
                improvements_text,
                generated,
                artifacts,
                project_path=project_path,
                branch_name=branch_name,
                stage="review",
                updated_at=state.generated_at,
            )

    if "security-audit" in scope.view_keys:
        security_records = [record for record in all_records if record.get("stage") == "security"]
        _write_generated(
            state.paths.branch_dir / "security-audit.md",
            render_security_artifact(
                security_records,
                state.generated_at,
                change_context=change_context,
                gate_summary=summaries["security_gate_summary"],
            ),
            generated,
            artifacts,
            project_path=project_path,
            branch_name=branch_name,
            stage="security",
            updated_at=state.generated_at,
        )

    MemoryStore(project_path).upsert_artifacts_batch(branch=branch_name, artifacts=artifacts)
    return generated
