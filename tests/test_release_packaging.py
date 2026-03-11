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
    assert len(archives) == 6

    with zipfile.ZipFile(archives[0]) as zf:
        names = set(zf.namelist())
        assert ".madspec/procedures/next-step-selection.md" in names
        assert ".madspec/templates/active-session-template.json" in names
        assert not any(name.startswith(".madspec/scripts/") for name in names)
        assert any(name.endswith("madspec.mvp.plan.md") or name.endswith("madspec.mvp.plan.agent.md") for name in names)
        assert any(name.startswith(".cursor/commands/") or name.startswith(".opencode/command/") or name.startswith(".github/agents/") for name in names)

        command_name = next(
            name
            for name in names
            if name.endswith("madspec.mvp.plan.md") or name.endswith("madspec.mvp.plan.agent.md")
        )
        command_body = zf.read(command_name).decode("utf-8")
        assert "scripts:" not in command_body
        assert "get-branch" not in command_body
        assert "--step-kind" in command_body
        assert "red -> green -> refactor" in command_body

        for stage_name in (
            "madspec.mvp.concept",
            "madspec.mvp.design",
            "madspec.mvp.tech",
            "madspec.mvp.architecture",
        ):
            stage_command = next(
                name
                for name in names
                if name.endswith(f"{stage_name}.md") or name.endswith(f"{stage_name}.agent.md")
            )
            stage_body = zf.read(stage_command).decode("utf-8")
            assert "madspec memory checkpoint" in stage_body
            if stage_name == "madspec.mvp.tech":
                assert "mvp.tech.json" in stage_body
                assert "tech_status" in stage_body
                assert "generated artifact" in stage_body
            if stage_name == "madspec.mvp.architecture":
                assert "mvp.architecture.json" in stage_body
                assert "architecture_status" in stage_body
                assert "--full-artifact" in stage_body
                assert "generated artifacts/views" in stage_body or "generated artifact" in stage_body

        implement_command = next(
            name
            for name in names
            if name.endswith("madspec.mvp.implement.md") or name.endswith("madspec.mvp.implement.agent.md")
        )
        implement_body = zf.read(implement_command).decode("utf-8")
        assert "madspec memory retrieve --stage mvp.implement" in implement_body
        assert "madspec memory start-step --stage mvp.implement" in implement_body
        assert "madspec memory checkpoint-step --stage mvp.implement" in implement_body
        assert "madspec memory complete-step --stage mvp.implement" in implement_body
        assert "Не редактируй `progress.json` вручную." in implement_body or "не редактируй `.madspec/<BRANCH>/memory/progress.json` вручную" in implement_body
        assert "implementation-context.md` и `project-context.md` являются generated views" in implement_body
        assert "После успешной валидации шага создай `.madspec/<BRANCH>/steps/step-[NN]-[name]/implementation-context.md`" not in implement_body
        assert "После создания коммита**: Обнови `implementation-context.md`" not in implement_body
