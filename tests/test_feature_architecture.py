from __future__ import annotations

import ast
import subprocess
from pathlib import Path


def _import_targets(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            targets.append(f"{'.' * node.level}{module}")
    return targets


def _assert_tree_has_no_import_segment(root: Path, *, forbidden_segment: str) -> None:
    for path in root.rglob("*.py"):
        for target in _import_targets(path):
            parts = target.lstrip(".").split(".")
            assert forbidden_segment not in parts, (
                f"{path.relative_to(root.parents[2])} imports forbidden segment "
                f"'{forbidden_segment}' via '{target}'"
            )


def test_feature_first_layout_exists() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli"
    assert (root / "features" / "init" / "cli.py").exists()
    assert (root / "features" / "git" / "cli.py").exists()
    assert (root / "features" / "meta" / "cli.py").exists()
    assert (root / "memory" / "cli" / "__init__.py").exists()
    assert (root / "shared" / "cli" / "json_output.py").exists()
    assert not (root / "commands").exists()


def test_memory_domain_is_decoupled_from_cli_frameworks() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "memory" / "domain"
    forbidden = ("typer", "rich", "httpx", "subprocess")
    for path in root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert f"import {token}" not in content
            assert f"from {token} import" not in content


def test_memory_root_contains_only_thin_facades() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "memory"
    allowed = {"__init__.py"}
    for path in root.glob("*.py"):
        if path.name in allowed:
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count <= 40, f"{path.name} is too large for a compatibility facade"


def test_memory_source_tree_has_no_pycache_dirs() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    memory_root = repo_root / "src" / "madspec_cli" / "memory"
    git_dir = repo_root / ".git"

    if git_dir.exists():
        result = subprocess.run(
            ["git", "ls-files", "src/madspec_cli/memory"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "__pycache__/" not in result.stdout
        return

    assert not any(memory_root.rglob("__pycache__"))


def test_system_store_is_packaged_behind_thin_facade() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "memory" / "shared"
    package_dir = root / "system_store"
    assert package_dir.is_dir()
    assert not (root / "system_store.py").exists()
    expected_modules = {
        "__init__.py",
        "constants.py",
        "jobs.py",
        "layout.py",
        "retrieval.py",
        "store.py",
        "sync.py",
        "text.py",
        "vector.py",
    }
    assert expected_modules.issubset({path.name for path in package_dir.glob("*.py")})
    line_count = len((package_dir / "__init__.py").read_text(encoding="utf-8").splitlines())
    assert line_count <= 40


def test_feature_cli_does_not_import_legacy_commands() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "features"
    for path in root.rglob("cli*.py"):
        content = path.read_text(encoding="utf-8")
        assert ".commands" not in content


def test_feature_domain_does_not_import_infrastructure() -> None:
    features_root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "features"
    for domain_root in features_root.glob("*/domain"):
        _assert_tree_has_no_import_segment(domain_root, forbidden_segment="infrastructure")


def test_feature_domain_does_not_import_cli() -> None:
    features_root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "features"
    for domain_root in features_root.glob("*/domain"):
        _assert_tree_has_no_import_segment(domain_root, forbidden_segment="cli")


def test_infrastructure_layers_do_not_import_presentation_primitives() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    roots = [
        repo_root / "src" / "madspec_cli" / "shared" / "infra",
        *sorted((repo_root / "src" / "madspec_cli" / "features").glob("*/infrastructure")),
    ]
    forbidden_tokens = (
        "import rich",
        "from rich",
        "import typer",
        "from typer",
        "console",
        "show_banner",
    )
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in content, f"{path.relative_to(repo_root)} should not depend on presentation token {token!r}"


def test_init_infrastructure_has_no_rich_or_cli_imports() -> None:
    path = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "features" / "init" / "infrastructure" / "initializer_core.py"
    content = path.read_text(encoding="utf-8")
    for token in ("from rich", "import rich", "StepTracker", "console.print", "show_banner"):
        assert token not in content


def test_agents_domain_is_decoupled_from_project_state_io() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "features" / "agents" / "domain"
    _assert_tree_has_no_import_segment(root, forbidden_segment="storage")
    _assert_tree_has_no_import_segment(root, forbidden_segment="project_state")


def test_gates_domain_does_not_import_application_or_infrastructure() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "features" / "gates" / "domain"
    _assert_tree_has_no_import_segment(root, forbidden_segment="application")
    _assert_tree_has_no_import_segment(root, forbidden_segment="infrastructure")


def test_refactor_facades_stay_thin() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    agents_storage = repo_root / "src" / "madspec_cli" / "features" / "agents" / "infrastructure" / "storage.py"
    gates_common = repo_root / "src" / "madspec_cli" / "features" / "gates" / "application" / "common.py"

    assert len(agents_storage.read_text(encoding="utf-8").splitlines()) <= 140
    assert len(gates_common.read_text(encoding="utf-8").splitlines()) <= 40


def test_runtime_code_does_not_depend_on_git_ops_shim() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli"
    for path in root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        assert "madspec_cli.git_ops" not in content
        assert "from .git_ops import" not in content
        assert "from ..git_ops import" not in content


def test_legacy_top_level_shims_are_removed() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli"
    assert not (root / "git_ops.py").exists()
    assert not (root / "initializer.py").exists()
