from __future__ import annotations

from pathlib import Path


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
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "memory"
    assert not any(root.rglob("__pycache__"))


def test_feature_cli_does_not_import_legacy_commands() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "madspec_cli" / "features"
    for path in root.rglob("cli*.py"):
        content = path.read_text(encoding="utf-8")
        assert ".commands" not in content


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
