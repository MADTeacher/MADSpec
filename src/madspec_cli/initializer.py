from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .github_api import (
    DEFAULT_SSL_CONTEXT,
    ReleaseAsset,
    _format_rate_limit_error,
    _github_auth_headers,
    create_http_client,
    fetch_latest_release_asset,
)
from .git_ops import get_current_branch, init_git_repo, is_git_repo
from .memory import consolidate_branch_memory, ensure_memory_layout, validate_branch_memory
from .project_state import create_madspec_config, ensure_branch_dir
from .ui import StepTracker, console


@dataclass(frozen=True)
class InitResult:
    project_path: Path
    selected_ai: str
    selected_script: str
    branch_name: str | None
    git_error_message: str | None
    config_error_message: str | None


def merge_json_files(
    existing_path: Path,
    new_content: dict,
    verbose: bool = False,
) -> dict:
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

    merged = deep_merge(existing_content, new_content)
    if verbose:
        console.print(f"[cyan]Merged JSON file:[/cyan] {existing_path.name}")
    return merged


def handle_vscode_settings(
    sub_item: Path,
    dest_file: Path,
    rel_path: Path,
    *,
    verbose: bool = False,
    tracker: StepTracker | None = None,
) -> None:
    def log(message: str, color: str = "green") -> None:
        if verbose and not tracker:
            console.print(f"[{color}]{message}[/] {rel_path}")

    try:
        new_settings = json.loads(sub_item.read_text(encoding="utf-8"))
        if dest_file.exists():
            merged = merge_json_files(dest_file, new_settings, verbose=verbose and not tracker)
            dest_file.write_text(json.dumps(merged, indent=4) + "\n", encoding="utf-8")
            log("Merged:", "green")
        else:
            shutil.copy2(sub_item, dest_file)
            log("Copied (no existing settings.json):", "blue")
    except Exception as exc:
        log(f"Warning: Could not merge, copying instead: {exc}", "yellow")
        shutil.copy2(sub_item, dest_file)


def download_template_from_github(
    ai_assistant: str,
    download_dir: Path,
    *,
    script_type: str = "sh",
    verbose: bool = True,
    show_progress: bool = True,
    client: httpx.Client | None = None,
    debug: bool = False,
    github_token: str | None = None,
) -> tuple[Path, ReleaseAsset]:
    repo_owner = "MADTeacher"
    repo_name = "MADSpec"
    http_client = client or create_http_client()
    pattern = f"madspec-template-{ai_assistant}-{script_type}"

    if verbose:
        console.print("[cyan]Fetching latest release information...[/cyan]")

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
        console.print(
            f"[red]No matching release asset found[/red] for [bold]{ai_assistant}[/bold] (expected pattern: [bold]{pattern}[/bold])"
        )
        console.print(
            Panel(str(exc), title="Available Assets", border_style="yellow")
        )
        raise RuntimeError("no matching release asset found") from exc
    except Exception as exc:
        console.print("[red]Error fetching release information[/red]")
        console.print(Panel(str(exc), title="Fetch Error", border_style="red"))
        raise

    if verbose:
        console.print(f"[cyan]Found template:[/cyan] {asset.filename}")
        console.print(f"[cyan]Size:[/cyan] {asset.size:,} bytes")
        console.print(f"[cyan]Release:[/cyan] {asset.release}")
        console.print("[cyan]Downloading template...[/cyan]")

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
                error_msg = _format_rate_limit_error(
                    response.status_code,
                    response.headers,
                    asset.asset_url,
                )
                if debug:
                    error_msg += f"\n\n[dim]Response body (truncated 400):[/dim]\n{response.text[:400]}"
                raise RuntimeError(error_msg)

            total_size = int(response.headers.get("content-length", 0))
            with zip_path.open("wb") as fh:
                if total_size == 0:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        fh.write(chunk)
                elif show_progress:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        console=console,
                    ) as progress:
                        task = progress.add_task("Downloading...", total=total_size)
                        downloaded = 0
                        for chunk in response.iter_bytes(chunk_size=8192):
                            fh.write(chunk)
                            downloaded += len(chunk)
                            progress.update(task, completed=downloaded)
                else:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        fh.write(chunk)
    except Exception as exc:
        console.print("[red]Error downloading template[/red]")
        if zip_path.exists():
            zip_path.unlink()
        console.print(Panel(str(exc), title="Download Error", border_style="red"))
        raise

    if verbose:
        console.print(f"Downloaded: {asset.filename}")

    return zip_path, asset


def download_and_extract_template(
    project_path: Path,
    ai_assistant: str,
    script_type: str,
    is_current_dir: bool = False,
    *,
    verbose: bool = True,
    tracker: StepTracker | None = None,
    client: httpx.Client | None = None,
    debug: bool = False,
    github_token: str | None = None,
) -> Path:
    current_dir = Path.cwd()

    if tracker:
        tracker.start("fetch", "contacting GitHub API")
    zip_path: Path | None = None
    try:
        zip_path, asset = download_template_from_github(
            ai_assistant,
            current_dir,
            script_type=script_type,
            verbose=verbose and tracker is None,
            show_progress=tracker is None,
            client=client,
            debug=debug,
            github_token=github_token,
        )
        if tracker:
            tracker.complete("fetch", f"release {asset.release} ({asset.size:,} bytes)")
            tracker.complete("download", asset.filename)
    except Exception as exc:
        if tracker:
            tracker.error("fetch", str(exc))
        raise

    if tracker:
        tracker.start("extract")
    elif verbose:
        console.print("Extracting template...")

    try:
        if not is_current_dir:
            project_path.mkdir(parents=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_contents = zip_ref.namelist()
            if tracker:
                tracker.complete("zip-list", f"{len(zip_contents)} entries")
            elif verbose:
                console.print(f"[cyan]ZIP contains {len(zip_contents)} items[/cyan]")

            if is_current_dir:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    zip_ref.extractall(temp_path)
                    extracted_items = list(temp_path.iterdir())
                    if tracker:
                        tracker.complete("extracted-summary", f"temp {len(extracted_items)} items")
                    elif verbose:
                        console.print(
                            f"[cyan]Extracted {len(extracted_items)} items to temp location[/cyan]"
                        )

                    source_dir = temp_path
                    if len(extracted_items) == 1 and extracted_items[0].is_dir():
                        source_dir = extracted_items[0]
                        if tracker:
                            tracker.complete("flatten")
                        elif verbose:
                            console.print("[cyan]Found nested directory structure[/cyan]")

                    for item in source_dir.iterdir():
                        dest_path = project_path / item.name
                        if item.is_dir():
                            if dest_path.exists():
                                if verbose and not tracker:
                                    console.print(f"[yellow]Merging directory:[/yellow] {item.name}")
                                for sub_item in item.rglob("*"):
                                    if not sub_item.is_file():
                                        continue
                                    rel_path = sub_item.relative_to(item)
                                    dest_file = dest_path / rel_path
                                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                                    if dest_file.name == "settings.json" and dest_file.parent.name == ".vscode":
                                        handle_vscode_settings(
                                            sub_item,
                                            dest_file,
                                            rel_path,
                                            verbose=verbose,
                                            tracker=tracker,
                                        )
                                    else:
                                        shutil.copy2(sub_item, dest_file)
                            else:
                                shutil.copytree(item, dest_path)
                        else:
                            if dest_path.exists() and verbose and not tracker:
                                console.print(f"[yellow]Overwriting file:[/yellow] {item.name}")
                            shutil.copy2(item, dest_path)
                    if verbose and not tracker:
                        console.print("[cyan]Template files merged into current directory[/cyan]")
            else:
                zip_ref.extractall(project_path)
                extracted_items = list(project_path.iterdir())
                if tracker:
                    tracker.complete("extracted-summary", f"{len(extracted_items)} top-level items")
                elif verbose:
                    console.print(
                        f"[cyan]Extracted {len(extracted_items)} items to {project_path}:[/cyan]"
                    )
                    for item in extracted_items:
                        console.print(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")

                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    nested_dir = extracted_items[0]
                    temp_move_dir = project_path.parent / f"{project_path.name}_temp"
                    shutil.move(str(nested_dir), str(temp_move_dir))
                    project_path.rmdir()
                    shutil.move(str(temp_move_dir), str(project_path))
                    if tracker:
                        tracker.complete("flatten")
                    elif verbose:
                        console.print("[cyan]Flattened nested directory structure[/cyan]")
    except Exception:
        if not is_current_dir and project_path.exists():
            shutil.rmtree(project_path)
        if tracker:
            tracker.error("extract", "failed")
        raise
    else:
        if tracker:
            tracker.complete("extract")
    finally:
        if zip_path and zip_path.exists():
            zip_path.unlink()
            if tracker:
                tracker.complete("cleanup")
            elif verbose:
                console.print(f"Cleaned up: {zip_path.name}")

    return project_path


def ensure_executable_scripts(
    project_path: Path,
    tracker: StepTracker | None = None,
) -> None:
    if os.name == "nt":
        return

    failures: list[str] = []
    updated = 0
    for root in (project_path / "scripts", project_path / ".madspec" / "scripts"):
        if not root.is_dir():
            continue
        for script in root.rglob("*.sh"):
            try:
                if script.is_symlink() or not script.is_file():
                    continue
                if script.read_bytes()[:2] != b"#!":
                    continue
                mode = script.stat().st_mode
                if mode & 0o111:
                    continue
                new_mode = mode
                if mode & 0o400:
                    new_mode |= 0o100
                if mode & 0o040:
                    new_mode |= 0o010
                if mode & 0o004:
                    new_mode |= 0o001
                if not (new_mode & 0o100):
                    new_mode |= 0o100
                os.chmod(script, new_mode)
                updated += 1
            except Exception as exc:
                failures.append(f"{script.relative_to(root)}: {exc}")

    if tracker:
        detail = f"{updated} updated" + (f", {len(failures)} failed" if failures else "")
        tracker.add("chmod", "Set script permissions recursively")
        (tracker.error if failures else tracker.complete)("chmod", detail)
        return

    if updated:
        console.print(f"[cyan]Updated execute permissions on {updated} script(s) recursively[/cyan]")
    if failures:
        console.print("[yellow]Some scripts could not be updated:[/yellow]")
        for failure in failures:
            console.print(f"  - {failure}")


def initialize_project(
    project_path: Path,
    *,
    selected_ai: str,
    selected_script: str,
    here: bool,
    no_git: bool,
    should_init_git: bool,
    skip_tls: bool,
    debug: bool,
    github_token: str | None,
    tracker: StepTracker | None = None,
) -> InitResult:
    verify = DEFAULT_SSL_CONTEXT if not skip_tls else False
    local_client = create_http_client(verify=verify)
    git_error_message: str | None = None
    config_error_message: str | None = None
    branch_name: str | None = None

    download_and_extract_template(
        project_path,
        selected_ai,
        selected_script,
        here,
        verbose=False,
        tracker=tracker,
        client=local_client,
        debug=debug,
        github_token=github_token,
    )
    ensure_executable_scripts(project_path, tracker=tracker)

    if tracker:
        tracker.add("madspec-config", "Create MADSpec config")

    try:
        branch_name = get_current_branch(project_path)
        create_madspec_config(project_path, branch_name)
        ensure_branch_dir(project_path, branch_name)
        ensure_memory_layout(project_path, branch_name)
        consolidate_branch_memory(project_path, branch_name)
        memory_errors = validate_branch_memory(project_path, branch_name)
        if memory_errors:
            raise RuntimeError("; ".join(memory_errors))
        if tracker:
            tracker.complete("madspec-config", f"branch: {branch_name}")
    except Exception as exc:
        config_error_message = str(exc)
        if tracker:
            tracker.error("madspec-config", f"config creation failed: {exc}")

    if tracker:
        tracker.start("git")
    if no_git:
        if tracker:
            tracker.skip("git", "--no-git flag")
    elif is_git_repo(project_path):
        if tracker:
            tracker.complete("git", "existing repo detected")
    elif should_init_git:
        success, error_msg = init_git_repo(project_path, quiet=True)
        if success:
            if tracker:
                tracker.complete("git", "initialized")
        else:
            git_error_message = error_msg
            if tracker:
                tracker.error("git", "init failed")
    elif tracker:
        tracker.skip("git", "git not available")

    return InitResult(
        project_path=project_path,
        selected_ai=selected_ai,
        selected_script=selected_script,
        branch_name=branch_name,
        git_error_message=git_error_message,
        config_error_message=config_error_message,
    )
