from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.memory import capture_stage_memory
from tests.support import (
    bootstrap_project,
    create_step_artifacts,
    step_metadata,
    step_status,
    write_concept_markdown,
)


@dataclass(slots=True)
class MemoryProjectHarness:
    project_path: Path
    paths: dict[str, Path]
    branch: str = "main"

    @property
    def branch_dir(self) -> Path:
        return self.paths["branch_dir"]

    def create_step_artifacts(self, step_id: str) -> None:
        create_step_artifacts(self.branch_dir, step_id)

    def write_mvp_concept(self) -> Path:
        return write_concept_markdown(self.branch_dir)

    def seed_concept_for_design(self) -> None:
        capture_stage_memory(
            self.project_path,
            self.branch,
            "mvp.concept",
            project_name="MVP scheduling assistant",
            system_overview="System helps freelancers manage bookings and reminders from one interface.",
            audiences=["Freelancers"],
            scenarios=["Book and reschedule client meetings"],
            pain_points=["Appointments are managed manually across chats and notes"],
            feature_p1=["Booking workflow::Capture booking details and send reminders"],
            feature_p2=["Profile studio::Customize the public-facing profile"],
            feature_p3=["Export hub::Download settings and summaries"],
            status="validated",
        )

    def write_design_prototypes(self) -> None:
        ui_dir = self.branch_dir / "ui-prototype"
        ui_dir.mkdir(parents=True, exist_ok=True)
        for name in ("index.html", "schedule-board.html", "profile-studio.html", "export-hub.html"):
            (ui_dir / name).write_text(f"<html><body>{name}</body></html>\n", encoding="utf-8")


def bootstrap_memory_project(tmp_path: Path, branch: str = "main") -> MemoryProjectHarness:
    paths = bootstrap_project(tmp_path, branch)
    return MemoryProjectHarness(
        project_path=paths["branch_dir"].parents[1],
        paths=paths,
        branch=branch,
    )

