from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from madspec_cli.memory import (  # noqa: E402
    append_jsonl,
    capture_stage_memory,
    checkpoint_stage_memory,
    ensure_memory_layout,
    get_memory_paths,
    make_record,
    retrieve_memory_context,
)


def _bootstrap_project(root: Path, branch: str = "main") -> dict[str, Path]:
    project_path = root / "project"
    project_path.mkdir()
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir()
    (madspec_dir / "config.json").write_text(
        json.dumps({"currentBranch": branch, "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    ensure_memory_layout(project_path, branch)
    return get_memory_paths(project_path, branch)


def _populate_records(paths: dict[str, Path], *, stage: str, records: int) -> None:
    append_jsonl(
        paths["facts"],
        [
            make_record(
                "main",
                stage,
                "benchmark",
                f"Fact #{index}",
                status="validated",
                evidence=["benchmark"],
                scope="project",
                semantic_kind="fact",
                record_type="fact",
            )
            for index in range(records)
        ],
    )
    append_jsonl(
        paths["decisions"],
        [
            make_record(
                "main",
                stage,
                "benchmark",
                f"Decision #{index}",
                status="validated",
                evidence=["benchmark"],
                scope="project",
                semantic_kind="decision",
                record_type="decision",
            )
            for index in range(records)
        ],
    )
    append_jsonl(
        paths["contracts"],
        [
            make_record(
                "main",
                stage,
                "benchmark",
                f"Contract #{index}",
                status="validated",
                evidence=["benchmark"],
                scope="project",
                semantic_kind="contract",
                record_type="contract",
            )
            for index in range(records)
        ],
    )
    append_jsonl(
        paths["decision_log"],
        [
            make_record(
                "main",
                stage,
                "benchmark",
                f"Decision log #{index}",
                status="validated",
                evidence=["benchmark"],
                scope="project",
                record_type="stage_note",
            )
            for index in range(records)
        ],
    )
    append_jsonl(
        paths["events"],
        [
            make_record(
                "main",
                stage,
                "benchmark",
                f"Event #{index}",
                status="validated",
                evidence=["benchmark"],
                scope="project",
                record_type="event",
            )
            for index in range(records)
        ],
    )


def _prepare_concept_baseline(paths: dict[str, Path], records: int) -> None:
    _populate_records(paths, stage="mvp.concept", records=records)
    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.concept",
        project_name="Benchmark scheduling assistant",
        system_overview="System helps freelancers manage bookings and reminders.",
        audiences=["Freelancers"],
        scenarios=["Book and reschedule client meetings"],
        pain_points=["Manual follow-ups cause missed appointments"],
        feature_p1=["Booking workflow::Create bookings and reminders"],
        status="validated",
    )


def _prepare_tech_baseline(paths: dict[str, Path], records: int) -> None:
    _populate_records(paths, stage="mvp.tech", records=records)
    capture_stage_memory(
        paths["branch_dir"].parents[1],
        "main",
        "mvp.tech",
        summary="Benchmark tech capture",
        facts=["Need web delivery and fast iteration"],
        decisions=["Use FastAPI for backend and HTMX for frontend"],
        contracts=["Python version must remain 3.13"],
        status="validated",
    )


def _measure_retrieve(stage: str, records: int, iterations: int) -> list[float]:
    durations: list[float] = []
    with tempfile.TemporaryDirectory() as tmp:
        paths = _bootstrap_project(Path(tmp))
        if stage == "mvp.concept":
            _prepare_concept_baseline(paths, records)
        else:
            _prepare_tech_baseline(paths, records)

        for _ in range(iterations):
            started_at = time.perf_counter()
            retrieve_memory_context(
                paths["branch_dir"].parents[1],
                "main",
                stage,
            )
            durations.append((time.perf_counter() - started_at) * 1000)
    return durations


def _measure_capture(stage: str, records: int, iterations: int) -> list[float]:
    durations: list[float] = []
    for _ in range(iterations):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _bootstrap_project(Path(tmp))
            if stage == "mvp.concept":
                _populate_records(paths, stage=stage, records=records)
                started_at = time.perf_counter()
                capture_stage_memory(
                    paths["branch_dir"].parents[1],
                    "main",
                    stage,
                    project_name="Benchmark scheduling assistant",
                    system_overview="System helps freelancers manage bookings and reminders.",
                    audiences=["Freelancers"],
                    scenarios=["Book and reschedule client meetings"],
                    pain_points=["Manual follow-ups cause missed appointments"],
                    feature_p1=["Booking workflow::Create bookings and reminders"],
                    status="validated",
                )
            else:
                _populate_records(paths, stage=stage, records=records)
                started_at = time.perf_counter()
                capture_stage_memory(
                    paths["branch_dir"].parents[1],
                    "main",
                    stage,
                    summary="Benchmark tech capture",
                    facts=["Need web delivery and fast iteration"],
                    decisions=["Use FastAPI for backend and HTMX for frontend"],
                    contracts=["Python version must remain 3.13"],
                    status="validated",
                )
            durations.append((time.perf_counter() - started_at) * 1000)
    return durations


def _measure_checkpoint(stage: str, records: int, iterations: int) -> list[float]:
    durations: list[float] = []
    for _ in range(iterations):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _bootstrap_project(Path(tmp))
            if stage == "mvp.concept":
                _prepare_concept_baseline(paths, records)
                started_at = time.perf_counter()
                checkpoint_stage_memory(
                    paths["branch_dir"].parents[1],
                    "main",
                    stage,
                    "Concept benchmark checkpoint",
                    evidence=[".madspec/main/concept.md"],
                )
            else:
                _prepare_tech_baseline(paths, records)
                started_at = time.perf_counter()
                checkpoint_stage_memory(
                    paths["branch_dir"].parents[1],
                    "main",
                    stage,
                    "Tech benchmark checkpoint",
                    evidence=[".madspec/main/project-context.md"],
                )
            durations.append((time.perf_counter() - started_at) * 1000)
    return durations


def _summarize(values: list[float]) -> dict[str, float]:
    return {
        "min_ms": round(min(values), 3),
        "mean_ms": round(statistics.mean(values), 3),
        "max_ms": round(max(values), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark MADSpec memory runtime operations.")
    parser.add_argument("--records", type=int, default=500, help="Number of synthetic records per memory file.")
    parser.add_argument("--iterations", type=int, default=5, help="Number of benchmark iterations.")
    parser.add_argument(
        "--output",
        choices=("json", "pretty"),
        default="pretty",
        help="Output format.",
    )
    args = parser.parse_args()

    results: dict[str, dict[str, dict[str, float]]] = {}
    for stage in ("mvp.concept", "mvp.tech"):
        results[stage] = {
            "retrieve": _summarize(_measure_retrieve(stage, args.records, args.iterations)),
            "capture": _summarize(_measure_capture(stage, args.records, args.iterations)),
            "checkpoint": _summarize(_measure_checkpoint(stage, args.records, args.iterations)),
        }

    payload = {
        "records": args.records,
        "iterations": args.iterations,
        "results": results,
    }

    if args.output == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"records={args.records} iterations={args.iterations}")
    for stage, stage_results in results.items():
        print(stage)
        for operation, stats in stage_results.items():
            print(
                f"  {operation}: min={stats['min_ms']}ms mean={stats['mean_ms']}ms max={stats['max_ms']}ms"
            )


if __name__ == "__main__":
    main()
