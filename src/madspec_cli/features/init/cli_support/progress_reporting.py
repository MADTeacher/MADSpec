from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from rich.live import Live

from madspec_cli.shared.cli.banners import StepTracker, console

from ..application.contracts import InitMemorySelection, InitProgressEvent, InitProgressReporter
from .memory_selection import memory_selection_summary

T = TypeVar("T")


class TrackerProgressReporter(InitProgressReporter):
    def __init__(self, tracker: StepTracker) -> None:
        self._tracker = tracker

    def handle(self, event: InitProgressEvent) -> None:
        if event.action == "start":
            self._tracker.start(event.step, event.detail)
        elif event.action == "complete":
            self._tracker.complete(event.step, event.detail)
        elif event.action == "skip":
            self._tracker.skip(event.step, event.detail or "")
        elif event.action == "error":
            self._tracker.error(event.step, event.detail or "")


def build_init_tracker(*, selected_ai: str, memory_selection: InitMemorySelection) -> StepTracker:
    tracker = StepTracker("Initialize MADSpec Project")
    for key, label, detail in (("precheck", "Check required tools", "ok"), ("ai-select", "Select AI assistant", selected_ai)):
        tracker.add(key, label)
        tracker.complete(key, detail)
    tracker.add("memory-select", "Choose memory embeddings")
    tracker.complete("memory-select", memory_selection_summary(memory_selection))
    for key, label in (
        ("memory-bootstrap", "Bootstrap memory model"),
        ("fetch", "Fetch latest release"),
        ("download", "Download template"),
        ("extract", "Extract template"),
        ("zip-list", "Archive contents"),
        ("extracted-summary", "Extraction summary"),
        ("flatten", "Flatten nested directory"),
        ("cleanup", "Cleanup"),
        ("madspec-config", "Create MADSpec config"),
        ("git", "Initialize git repository"),
        ("final", "Finalize"),
    ):
        tracker.add(key, label)
    return tracker


def run_with_tracker(tracker: StepTracker, action: Callable[[], T]) -> T:
    with Live(tracker.render(), console=console, refresh_per_second=8, transient=True) as live:
        tracker.attach_refresh(lambda: live.update(tracker.render()))
        return action()
