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
    assert len(archives) == 7

    qwen_archive = archive_dir / f"madspec-template-qwen-{tag}.zip"
    assert qwen_archive.exists()
    cursor_archive = archive_dir / f"madspec-template-cursor-agent-{tag}.zip"
    opencode_archive = archive_dir / f"madspec-template-opencode-{tag}.zip"
    copilot_archive = archive_dir / f"madspec-template-copilot-{tag}.zip"

    with zipfile.ZipFile(archives[0]) as zf:
        names = set(zf.namelist())
        assert ".madspec/procedures/next-step-selection.md" in names
        assert ".madspec/templates/active-session-template.json" in names
        assert ".madspec/templates/ui-storyboard-contract.md" in names
        assert ".madspec/templates/html-prototype-template.html" not in names
        assert ".madspec/templates/index-prototype-template.html" not in names
        assert not any(name.startswith(".madspec/scripts/") for name in names)
        assert any(name.endswith("madspec.mvp.plan.md") or name.endswith("madspec.mvp.plan.agent.md") for name in names)
        assert any(name.startswith(".cursor/commands/") or name.startswith(".opencode/commands/") or name.startswith(".github/agents/") for name in names)

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

        command_files = [
            name
            for name in names
            if name.startswith((".cursor/commands/", ".opencode/commands/", ".kilocode/rules/", ".roo/rules/", ".codeassistant/commands/", ".github/agents/"))
            and "/madspec." in name
            and (name.endswith(".md") or name.endswith(".agent.md"))
        ]
        assert command_files
        for packaged_command in command_files:
            packaged_body = zf.read(packaged_command).decode("utf-8")
            assert "madspec-cli-operator" in packaged_body

        policy_command = next(
            name
            for name in names
            if name.endswith("madspec.policy.md") or name.endswith("madspec.policy.agent.md")
        )
        policy_body = zf.read(policy_command).decode("utf-8")
        assert "policy-engine" in policy_body
        assert "madspec policy propose" in policy_body
        assert "madspec policy apply" in policy_body
        assert any(name.endswith("policy-engine/SKILL.md") for name in names)

        change_command = next(
            name
            for name in names
            if name.endswith("madspec.change.md") or name.endswith("madspec.change.agent.md")
        )
        change_body = zf.read(change_command).decode("utf-8")
        assert "change-engine" in change_body
        assert "madspec change preview" in change_body
        assert "madspec change apply" in change_body
        assert "madspec change verify" in change_body
        assert any(name.endswith("change-engine/SKILL.md") for name in names)

        gate_command = next(
            name
            for name in names
            if name.endswith("madspec.gate.md") or name.endswith("madspec.gate.agent.md")
        )
        gate_body = zf.read(gate_command).decode("utf-8")
        assert "gate-orchestrator" in gate_body
        assert "madspec gate status" in gate_body
        assert "madspec gate apply-waiver" in gate_body
        assert any(name.endswith("gate-orchestrator/SKILL.md") for name in names)

        memory_command = next(
            name
            for name in names
            if name.endswith("madspec.memory.md") or name.endswith("madspec.memory.agent.md")
        )
        memory_body = zf.read(memory_command).decode("utf-8")
        assert "memory-explain" in memory_body
        assert "madspec memory doctor" in memory_body
        assert "madspec memory explain" in memory_body
        assert any(name.endswith("memory-explain/SKILL.md") for name in names)

        merge_command = next(
            name
            for name in names
            if name.endswith("madspec.merge.md") or name.endswith("madspec.merge.agent.md")
        )
        merge_body = zf.read(merge_command).decode("utf-8")
        assert "merge-assistant" in merge_body
        assert "madspec memory compare-branches" in merge_body
        assert "madspec memory merge-branches" in merge_body
        assert any(name.endswith("merge-assistant/SKILL.md") for name in names)

        agents_command = next(
            name
            for name in names
            if name.endswith("madspec.agents.md") or name.endswith("madspec.agents.agent.md")
        )
        agents_body = zf.read(agents_command).decode("utf-8")
        assert "subagent-role-advisor" in agents_body
        assert "madspec agents profile" in agents_body
        assert "madspec agents subagents create" in agents_body
        assert "madspec agents subagents update" in agents_body
        assert "madspec agents subagents remove" in agents_body
        assert "madspec agents subagents context" in agents_body
        assert any(name.endswith("subagent-role-advisor/SKILL.md") for name in names)

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
            assert "madspec-cli-operator" in stage_body
            assert "--toon-output" in stage_body
            if stage_name == "madspec.mvp.tech":
                assert "mvp.tech.json" in stage_body
                assert "tech_status" in stage_body
                assert "generated artifact" in stage_body
            if stage_name == "madspec.mvp.design":
                assert "frontend-design" in stage_body
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
        assert "--toon-output" in implement_body
        assert "madspec memory start-step --stage mvp.implement" in implement_body
        assert "madspec memory checkpoint-step --stage mvp.implement" in implement_body
        assert "madspec memory complete-step --stage mvp.implement" in implement_body
        assert "madspec-cli-operator" in implement_body
        assert "Не редактируй `progress.json` вручную." in implement_body or "не редактируй `.madspec/<BRANCH>/memory/progress.json` вручную" in implement_body
        assert "implementation-context.md` и `project-context.md` являются generated views" in implement_body
        assert "После успешной валидации шага создай `.madspec/<BRANCH>/steps/step-[NN]-[name]/implementation-context.md`" not in implement_body
        assert "После создания коммита**: Обнови `implementation-context.md`" not in implement_body

        feature_init_command = next(
            name
            for name in names
            if name.endswith("madspec.feature.init.md") or name.endswith("madspec.feature.init.agent.md")
        )
        feature_init_body = zf.read(feature_init_command).decode("utf-8")
        assert "madspec memory retrieve --stage feature.init" in feature_init_body
        assert "--toon-output" in feature_init_body
        assert "madspec memory capture --stage feature.init" in feature_init_body
        assert "madspec memory checkpoint --stage feature.init" in feature_init_body
        assert "madspec-cli-operator" in feature_init_body
        assert ".madspec/<BRANCH>/memory/stages/feature.init.json" in feature_init_body
        assert ".madspec/feature/" not in feature_init_body

        feature_plan_command = next(
            name
            for name in names
            if name.endswith("madspec.feature.plan.md") or name.endswith("madspec.feature.plan.agent.md")
        )
        feature_plan_body = zf.read(feature_plan_command).decode("utf-8")
        assert "madspec memory retrieve --stage feature.plan" in feature_plan_body
        assert "--toon-output" in feature_plan_body
        assert "madspec memory register-step --stage feature.plan" in feature_plan_body
        assert "madspec-cli-operator" in feature_plan_body
        assert ".madspec/<BRANCH>/memory/stages/feature.plan.json" in feature_plan_body
        assert "generated views" in feature_plan_body

        deploy_command = next(
            name
            for name in names
            if name.endswith("madspec.deploy.md") or name.endswith("madspec.deploy.agent.md")
        )
        deploy_body = zf.read(deploy_command).decode("utf-8")
        assert "madspec memory retrieve --stage deploy --toon-output" in deploy_body
        assert "madspec memory capture --stage deploy" in deploy_body
        assert "madspec memory checkpoint --stage deploy" in deploy_body
        assert "madspec-cli-operator" in deploy_body
        assert "План развертывания" in deploy_body or "развертывания" in deploy_body

        feature_implement_command = next(
            name
            for name in names
            if name.endswith("madspec.feature.implement.md") or name.endswith("madspec.feature.implement.agent.md")
        )
        feature_implement_body = zf.read(feature_implement_command).decode("utf-8")
        assert "madspec memory retrieve --stage feature.implement" in feature_implement_body
        assert "--toon-output" in feature_implement_body
        assert "madspec memory start-step --stage feature.implement" in feature_implement_body
        assert "madspec memory checkpoint-step --stage feature.implement" in feature_implement_body
        assert "madspec memory complete-step --stage feature.implement" in feature_implement_body
        assert "madspec-cli-operator" in feature_implement_body
        assert "implementation-context.md` и `project-context.md` являются generated views" in feature_implement_body

        review_command = next(
            name
            for name in names
            if name.endswith("madspec.review.md") or name.endswith("madspec.review.agent.md")
        )
        review_body = zf.read(review_command).decode("utf-8")
        assert "madspec memory retrieve --stage review --toon-output" in review_body
        assert "madspec review status --toon-output" in review_body
        assert "madspec policy validate --stage review --toon-output" in review_body

        security_command = next(
            name
            for name in names
            if name.endswith("madspec.security.md") or name.endswith("madspec.security.agent.md")
        )
        security_body = zf.read(security_command).decode("utf-8")
        assert "madspec memory retrieve --stage security --toon-output" in security_body
        assert "madspec security status --toon-output" in security_body

    with zipfile.ZipFile(qwen_archive) as zf:
        names = set(zf.namelist())
        assert any(name.startswith(".qwen/commands/") for name in names)
        assert any(name.startswith(".qwen/agents/") for name in names)
        assert ".qwen/agents/madspec-developer.md" in names
        assert ".qwen/agents/madspec-contracts-data.md" in names
        assert ".qwen/agents/madspec-docs.md" in names
        qwen_command = next(name for name in names if name.endswith("madspec.mvp.concept.md"))
        qwen_body = zf.read(qwen_command).decode("utf-8")
        assert "{{args}}" in qwen_body
        assert "$ARGUMENTS" not in qwen_body
        assert "madspec-cli-operator" in qwen_body
        qwen_subagent = zf.read(".qwen/agents/madspec-security.md").decode("utf-8")
        assert "name: Специалист по безопасности" in qwen_subagent
        assert 'tools: ["read_file", "glob", "grep_search", "run_shell_command"]' in qwen_subagent
        assert "madspec agents subagents context --subagent-id security --toon-output" in qwen_subagent
        qwen_developer = zf.read(".qwen/agents/madspec-developer.md").decode("utf-8")
        assert "name: Специалист по разработке" in qwen_developer
        assert 'tools: ["read_file", "glob", "grep_search", "edit", "write_file", "run_shell_command"]' in qwen_developer

    with zipfile.ZipFile(cursor_archive) as zf:
        names = set(zf.namelist())
        assert any(name.startswith(".cursor/agents/") for name in names)
        cursor_subagent = zf.read(".cursor/agents/madspec-architecture.md").decode("utf-8")
        assert "execution_mode_hint: sequential" in cursor_subagent
        assert "tools:" not in cursor_subagent
        assert "madspec agents subagents context --subagent-id architecture --toon-output" in cursor_subagent
        cursor_developer = zf.read(".cursor/agents/madspec-developer.md").decode("utf-8")
        assert 'dependencies: ["architecture"]' in cursor_developer

    with zipfile.ZipFile(opencode_archive) as zf:
        names = set(zf.namelist())
        assert any(name.startswith(".opencode/commands/") for name in names)
        assert not any(name.startswith(".opencode/command/") for name in names)
        assert any(name.startswith(".opencode/agents/") for name in names)
        opencode_subagent = zf.read(".opencode/agents/madspec-testing.md").decode("utf-8")
        assert "mode: subagent" in opencode_subagent
        assert "hidden: true" in opencode_subagent
        assert "  edit: true" in opencode_subagent
        assert "  write: true" in opencode_subagent
        assert "  bash: true" in opencode_subagent
        opencode_docs = zf.read(".opencode/agents/madspec-docs.md").decode("utf-8")
        assert "name: Специалист по документации" in opencode_docs
        assert "  edit: true" in opencode_docs
        assert "  write: true" in opencode_docs
        assert "  bash: false" in opencode_docs

    with zipfile.ZipFile(copilot_archive) as zf:
        names = set(zf.namelist())
        assert any(name.startswith(".github/agents/madspec-") for name in names)
        copilot_subagent = zf.read(".github/agents/madspec-security.agent.md").decode("utf-8")
        assert "target: vscode" in copilot_subagent
        assert "user-invocable: false" in copilot_subagent
        assert 'tools: ["read", "search", "terminal"]' in copilot_subagent
        copilot_contracts = zf.read(".github/agents/madspec-contracts-data.agent.md").decode("utf-8")
        assert "name: Специалист по контрактам и данным" in copilot_contracts
        assert 'tools: ["read", "search"]' in copilot_contracts
        assert any(name.startswith(".github/prompts/madspec-security.prompt.md") for name in names)
