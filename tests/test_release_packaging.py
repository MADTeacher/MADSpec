from __future__ import annotations

import subprocess
import zipfile


def test_release_packaging_includes_memory_assets(repo_root) -> None:
    subprocess.run(
        ["bash", ".github/workflows/scripts/create-release-packages.sh", "v0.3.0"],
        cwd=repo_root,
        check=True,
        text=True,
    )

    archive_dir = repo_root / ".genreleases"
    archives = sorted(archive_dir.glob("madspec-template-*-v0.3.0.zip"))
    assert len(archives) == 12

    with zipfile.ZipFile(archives[0]) as zf:
        names = set(zf.namelist())
        assert ".madspec/procedures/next-step-selection.md" in names
        assert ".madspec/templates/active-session-template.json" in names
        assert any(name.endswith("madspec.mvp.plan.md") or name.endswith("madspec.mvp.plan.agent.md") for name in names)
        assert any(name.startswith(".cursor/commands/") or name.startswith(".opencode/command/") or name.startswith(".github/agents/") for name in names)
