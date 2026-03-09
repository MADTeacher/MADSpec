from __future__ import annotations

import subprocess
import tomllib
import zipfile


def test_release_packaging_includes_memory_assets(repo_root) -> None:
    version = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    tag = f"v{version}"
    subprocess.run(
        ["bash", ".github/workflows/scripts/create-release-packages.sh", tag],
        cwd=repo_root,
        check=True,
        text=True,
    )

    archive_dir = repo_root / ".genreleases"
    archives = sorted(archive_dir.glob(f"madspec-template-*-{tag}.zip"))
    assert len(archives) == 12

    with zipfile.ZipFile(archives[0]) as zf:
        names = set(zf.namelist())
        assert ".madspec/procedures/next-step-selection.md" in names
        assert ".madspec/templates/active-session-template.json" in names
        assert any(name.endswith("madspec.mvp.plan.md") or name.endswith("madspec.mvp.plan.agent.md") for name in names)
        assert any(name.startswith(".cursor/commands/") or name.startswith(".opencode/command/") or name.startswith(".github/agents/") for name in names)
