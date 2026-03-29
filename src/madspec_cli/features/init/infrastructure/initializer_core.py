from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from madspec_cli.memory.application.branch_state import BootstrapBranchStateRequest, bootstrap_branch_state, refresh_branch_state
from madspec_cli.memory.shared.validation import validate_branch_memory
from madspec_cli.memory.shared.system_store.model_bootstrap import ensure_model_available
from madspec_cli.memory.shared.system_store.provider_factory import resolve_configured_embeddings
from madspec_cli.shared.infra.github_client import (
    DEFAULT_SSL_CONTEXT,
    ReleaseAsset,
    _format_rate_limit_error,
    _github_auth_headers,
    create_http_client,
    fetch_latest_release_asset,
)


ProgressEmitter = Callable[[str, str, str | None], None]


@dataclass(frozen=True)
class InitResult:
    project_path: Path
    selected_ai: str
    branch_name: str | None
    git_error_message: str | None
    config_error_message: str | None
    memory_bootstrap: dict[str, object] | None = None


def _emit_progress(
    emit_progress: ProgressEmitter | None,
    action: str,
    step: str,
    detail: str | None = None,
) -> None:
    if emit_progress is not None:
        emit_progress(action, step, detail)


def merge_json_files(existing_path: Path, new_content: dict, verbose: bool = False) -> dict:
    del verbose
    try:
        existing_content = json.loads(existing_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return new_content

    def deep_merge(base: dict, update: dict) -> dict:
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    return deep_merge(existing_content, new_content)


def handle_vscode_settings(
    sub_item: Path,
    dest_file: Path,
    rel_path: Path,
    *,
    verbose: bool = False,
) -> None:
    del rel_path, verbose
    try:
        new_settings = json.loads(sub_item.read_text(encoding="utf-8"))
        if dest_file.exists():
            merged = merge_json_files(dest_file, new_settings)
            dest_file.write_text(json.dumps(merged, indent=4) + "\n", encoding="utf-8")
        else:
            shutil.copy2(sub_item, dest_file)
    except Exception:
        shutil.copy2(sub_item, dest_file)


def download_template_from_github(
    ai_assistant: str,
    download_dir: Path,
    *,
    verbose: bool = True,
    show_progress: bool = True,
    client: httpx.Client | None = None,
    debug: bool = False,
    github_token: str | None = None,
) -> tuple[Path, ReleaseAsset]:
    del verbose, show_progress
    repo_owner = "MADTeacher"
    repo_name = "MADSpec"
    http_client = client or create_http_client()
    pattern = f"madspec-template-{ai_assistant}"

    try:
        asset = fetch_latest_release_asset(
            repo_owner,
            repo_name,
            pattern,
            client=http_client,
            github_token=github_token,
            debug=debug,
        )
    except LookupError as exc:
        raise RuntimeError(
            f"No matching release asset found for {ai_assistant} (expected pattern: {pattern})\n{exc}"
        ) from exc

    zip_path = download_dir / asset.filename
    try:
        with http_client.stream(
            "GET",
            asset.asset_url,
            timeout=60,
            follow_redirects=True,
            headers=_github_auth_headers(github_token),
        ) as response:
            if response.status_code != 200:
                error_msg = _format_rate_limit_error(response.status_code, response.headers, asset.asset_url)
                if debug:
                    error_msg += f"\n\nResponse body (truncated 400):\n{response.text[:400]}"
                raise RuntimeError(error_msg)

            with zip_path.open("wb") as fh:
                for chunk in response.iter_bytes(chunk_size=8192):
                    fh.write(chunk)
    except Exception:
        if zip_path.exists():
            zip_path.unlink()
        raise

    return zip_path, asset


def download_and_extract_template(
    project_path: Path,
    ai_assistant: str,
    is_current_dir: bool = False,
    *,
    verbose: bool = True,
    emit_progress: ProgressEmitter | None = None,
    client: httpx.Client | None = None,
    debug: bool = False,
    github_token: str | None = None,
) -> Path:
    del verbose
    current_dir = Path.cwd()
    zip_path: Path | None = None
    _emit_progress(emit_progress, "start", "fetch", "contacting GitHub API")
    try:
        zip_path, asset = download_template_from_github(
            ai_assistant,
            current_dir,
            client=client,
            debug=debug,
            github_token=github_token,
        )
        _emit_progress(emit_progress, "complete", "fetch", f"release {asset.release} ({asset.size:,} bytes)")
        _emit_progress(emit_progress, "complete", "download", asset.filename)
    except Exception as exc:
        _emit_progress(emit_progress, "error", "fetch", str(exc))
        raise

    _emit_progress(emit_progress, "start", "extract")
    try:
        if not is_current_dir:
            project_path.mkdir(parents=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_contents = zip_ref.namelist()
            _emit_progress(emit_progress, "complete", "zip-list", f"{len(zip_contents)} entries")

            if is_current_dir:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    zip_ref.extractall(temp_path)
                    extracted_items = list(temp_path.iterdir())
                    _emit_progress(
                        emit_progress,
                        "complete",
                        "extracted-summary",
                        f"temp {len(extracted_items)} items",
                    )
                    source_dir = temp_path
                    if len(extracted_items) == 1 and extracted_items[0].is_dir():
                        source_dir = extracted_items[0]
                        _emit_progress(emit_progress, "complete", "flatten")

                    for item in source_dir.iterdir():
                        dest_path = project_path / item.name
                        if item.is_dir():
                            if dest_path.exists():
                                for sub_item in item.rglob("*"):
                                    if not sub_item.is_file():
                                        continue
                                    rel_path = sub_item.relative_to(item)
                                    dest_file = dest_path / rel_path
                                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                                    if dest_file.name == "settings.json" and dest_file.parent.name == ".vscode":
                                        handle_vscode_settings(sub_item, dest_file, rel_path)
                                    else:
                                        shutil.copy2(sub_item, dest_file)
                            else:
                                shutil.copytree(item, dest_path)
                        else:
                            shutil.copy2(item, dest_path)
            else:
                zip_ref.extractall(project_path)
                extracted_items = list(project_path.iterdir())
                _emit_progress(
                    emit_progress,
                    "complete",
                    "extracted-summary",
                    f"{len(extracted_items)} top-level items",
                )
                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    nested_dir = extracted_items[0]
                    temp_move_dir = project_path.parent / f"{project_path.name}_temp"
                    shutil.move(str(nested_dir), str(temp_move_dir))
                    project_path.rmdir()
                    shutil.move(str(temp_move_dir), str(project_path))
                    _emit_progress(emit_progress, "complete", "flatten")
    except Exception as exc:
        if not is_current_dir and project_path.exists():
            shutil.rmtree(project_path)
        _emit_progress(emit_progress, "error", "extract", str(exc))
        raise
    else:
        _emit_progress(emit_progress, "complete", "extract")
    finally:
        if zip_path and zip_path.exists():
            zip_path.unlink()
            _emit_progress(emit_progress, "complete", "cleanup")

    return project_path


def initialize_project(
    project_path: Path,
    *,
    selected_ai: str,
    memory_embeddings: dict[str, object] | None,
    here: bool,
    no_git: bool,
    should_init_git: bool,
    skip_tls: bool,
    debug: bool,
    github_token: str | None,
    emit_progress: ProgressEmitter | None = None,
) -> InitResult:
    verify = DEFAULT_SSL_CONTEXT if not skip_tls else False
    local_client = create_http_client(verify=verify)
    git_error_message: str | None = None
    config_error_message: str | None = None
    branch_name: str | None = None
    memory_bootstrap: dict[str, object] | None = None

    download_and_extract_template(
        project_path,
        selected_ai,
        here,
        emit_progress=emit_progress,
        client=local_client,
        debug=debug,
        github_token=github_token,
    )

    from madspec_cli.features.agents.infrastructure.storage import ensure_agents_layout, render_workspace_agents
    from madspec_cli.features.git.infrastructure.operations import get_current_branch, init_git_repo, is_git_repo
    from madspec_cli.features.policy.application.common import evaluate_branch_policies
    from madspec_cli.features.policy.infrastructure.storage import ensure_policy_layout

    _emit_progress(emit_progress, "start", "madspec-config")
    try:
        branch_name = get_current_branch(project_path)
        bootstrap_branch_state(
            BootstrapBranchStateRequest(
                project_path=project_path,
                branch_name=branch_name,
                agent_environment=selected_ai,
                memory_embeddings=memory_embeddings,
            )
        )
        embeddings_config = dict(memory_embeddings or {})
        provider = str(embeddings_config.get("provider") or "hash")
        download_policy = str(embeddings_config.get("downloadPolicy") or "none")
        if provider == "local-hf-onnx" and download_policy == "on-init":
            _emit_progress(emit_progress, "start", "memory-bootstrap", str(embeddings_config.get("model") or "dense"))
            ensure_model_available(project_path, embeddings_config, allow_download=True)
            _emit_progress(emit_progress, "complete", "memory-bootstrap", "downloaded")
        elif provider == "local-hf-onnx":
            _emit_progress(emit_progress, "skip", "memory-bootstrap", "deferred")
        else:
            _emit_progress(emit_progress, "skip", "memory-bootstrap", "not required")
        memory_bootstrap = resolve_configured_embeddings(project_path).to_status_payload(project_path)
        ensure_policy_layout(project_path)
        agents_state, _ = ensure_agents_layout(project_path, environment_id=selected_ai)
        render_workspace_agents(project_path, agents_state)
        refresh_branch_state(project_path, branch_name, full=True)
        init_policy_payload = evaluate_branch_policies(
            project_path,
            branch_name,
            stage=None,
            operation="validate",
            include_system_policies=False,
            create_policy_if_missing=False,
        )
        memory_errors = validate_branch_memory(
            project_path, branch_name,
            policy_violations=init_policy_payload["violations"],
        )
        if memory_errors:
            raise RuntimeError("; ".join(memory_errors))
        _emit_progress(emit_progress, "complete", "madspec-config", f"branch: {branch_name}")
    except Exception as exc:
        config_error_message = str(exc)
        _emit_progress(emit_progress, "error", "madspec-config", f"config creation failed: {exc}")

    _emit_progress(emit_progress, "start", "git")
    if no_git:
        _emit_progress(emit_progress, "skip", "git", "--no-git flag")
    elif is_git_repo(project_path):
        _emit_progress(emit_progress, "complete", "git", "existing repo detected")
    elif should_init_git:
        success, error_msg = init_git_repo(project_path, quiet=True)
        if success:
            _emit_progress(emit_progress, "complete", "git", "initialized")
        else:
            git_error_message = error_msg
            _emit_progress(emit_progress, "error", "git", "init failed")
    else:
        _emit_progress(emit_progress, "skip", "git", "git not available")

    return InitResult(
        project_path=project_path,
        selected_ai=selected_ai,
        branch_name=branch_name,
        git_error_message=git_error_message,
        config_error_message=config_error_message,
        memory_bootstrap=memory_bootstrap,
    )
