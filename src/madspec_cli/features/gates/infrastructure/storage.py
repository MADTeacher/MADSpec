from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.memory.shared.storage import now_iso


GATE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GatePaths:
    branch_dir: Path
    gates_dir: Path
    state_file: Path
    proposals_file: Path
    history_file: Path


def get_gate_paths(project_path: Path, branch_name: str) -> GatePaths:
    branch_dir = project_path / ".madspec" / branch_name
    gates_dir = branch_dir / "gates"
    return GatePaths(
        branch_dir=branch_dir,
        gates_dir=gates_dir,
        state_file=gates_dir / "state.json",
        proposals_file=gates_dir / "proposals.jsonl",
        history_file=gates_dir / "history.jsonl",
    )


def default_gate_state(branch_name: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "schemaVersion": GATE_SCHEMA_VERSION,
        "branch": branch_name,
        "revision": 1,
        "createdAt": ts,
        "updatedAt": ts,
        "waivers": [],
    }


def read_json(path: Path, default: Any) -> Any:
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


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def ensure_gate_layout(project_path: Path, branch_name: str) -> list[Path]:
    paths = get_gate_paths(project_path, branch_name)
    created: list[Path] = []
    if not paths.branch_dir.exists():
        paths.branch_dir.mkdir(parents=True, exist_ok=True)
        created.append(paths.branch_dir)
    if not paths.gates_dir.exists():
        paths.gates_dir.mkdir(parents=True, exist_ok=True)
        created.append(paths.gates_dir)
    if not paths.state_file.exists():
        write_json(paths.state_file, default_gate_state(branch_name))
        created.append(paths.state_file)
    if not paths.proposals_file.exists():
        paths.proposals_file.write_text("", encoding="utf-8")
        created.append(paths.proposals_file)
    if not paths.history_file.exists():
        paths.history_file.write_text("", encoding="utf-8")
        created.append(paths.history_file)
    return created


def load_gate_state(project_path: Path, branch_name: str) -> dict[str, Any]:
    ensure_gate_layout(project_path, branch_name)
    state = read_json(get_gate_paths(project_path, branch_name).state_file, default_gate_state(branch_name))
    if not isinstance(state, dict):
        state = default_gate_state(branch_name)
    if state.get("branch") != branch_name:
        state["branch"] = branch_name
    if not isinstance(state.get("waivers"), list):
        state["waivers"] = []
    if not isinstance(state.get("revision"), int) or state.get("revision", 0) <= 0:
        state["revision"] = 1
    if not state.get("createdAt"):
        state["createdAt"] = now_iso()
    if not state.get("updatedAt"):
        state["updatedAt"] = now_iso()
    return state


def save_gate_state(project_path: Path, branch_name: str, state: dict[str, Any]) -> dict[str, Any]:
    paths = get_gate_paths(project_path, branch_name)
    paths.gates_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths.state_file, state)
    if not paths.proposals_file.exists():
        paths.proposals_file.write_text("", encoding="utf-8")
    if not paths.history_file.exists():
        paths.history_file.write_text("", encoding="utf-8")
    return state


def list_gate_proposals(project_path: Path, branch_name: str) -> list[dict[str, Any]]:
    ensure_gate_layout(project_path, branch_name)
    return read_jsonl(get_gate_paths(project_path, branch_name).proposals_file)


def save_gate_proposals(project_path: Path, branch_name: str, proposals: list[dict[str, Any]]) -> None:
    ensure_gate_layout(project_path, branch_name)
    write_jsonl(get_gate_paths(project_path, branch_name).proposals_file, proposals)


def append_gate_proposal(project_path: Path, branch_name: str, proposal: dict[str, Any]) -> None:
    ensure_gate_layout(project_path, branch_name)
    append_jsonl(get_gate_paths(project_path, branch_name).proposals_file, proposal)


def list_gate_history(project_path: Path, branch_name: str) -> list[dict[str, Any]]:
    ensure_gate_layout(project_path, branch_name)
    return read_jsonl(get_gate_paths(project_path, branch_name).history_file)


def append_gate_history(project_path: Path, branch_name: str, event: dict[str, Any]) -> None:
    ensure_gate_layout(project_path, branch_name)
    append_jsonl(get_gate_paths(project_path, branch_name).history_file, event)
