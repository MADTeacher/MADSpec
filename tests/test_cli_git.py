from __future__ import annotations

import json


def test_git_current_branch_uses_config_fallback_json(make_madspec_project, invoke_cli) -> None:
    make_madspec_project(branch="feature/fallback")

    result = invoke_cli(["git", "current-branch", "--json-output"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload == {"branch": "feature/fallback", "source": "config"}


def test_git_set_branch_and_list_branches_json(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)

    main_result = invoke_cli(["git", "set-branch", "main", "--json-output"])
    feature_result = invoke_cli(["git", "set-branch", "feature/new-ui", "--json-output"])
    list_result = invoke_cli(["git", "list-branches", "--json-output"])

    assert main_result.exit_code == 0, main_result.stdout
    assert feature_result.exit_code == 0, feature_result.stdout
    assert list_result.exit_code == 0, list_result.stdout

    feature_payload = json.loads(feature_result.stdout)
    assert feature_payload["branch"] == "feature/new-ui"
    assert (tmp_path / ".madspec" / "feature/new-ui" / "memory" / "progress.json").exists()

    list_payload = json.loads(list_result.stdout)
    branch_names = {branch["name"] for branch in list_payload["branches"]}
    assert {"main", "feature/new-ui"} == branch_names


def test_git_init_create_branch_commit_and_current_branch_json(
    tmp_path,
    monkeypatch,
    invoke_cli,
    git_identity_env,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")

    init_result = invoke_cli(["git", "init", "--json-output"], env=git_identity_env)

    assert init_result.exit_code == 0, init_result.stdout
    init_payload = json.loads(init_result.stdout)
    assert init_payload["initialized"] is True
    assert init_payload["already_initialized"] is False
    assert (tmp_path / ".gitignore").exists()

    branch_result = invoke_cli(["git", "create-branch", "feature/auth", "--json-output"])
    current_result = invoke_cli(["git", "current-branch", "--json-output"])

    assert branch_result.exit_code == 0, branch_result.stdout
    assert current_result.exit_code == 0, current_result.stdout
    assert json.loads(current_result.stdout) == {"branch": "feature/auth", "source": "git"}

    (tmp_path / "README.md").write_text("# demo\n\nupdated\n", encoding="utf-8")
    commit_result = invoke_cli(
        ["git", "commit", "--message", "feat: update readme", "--json-output"],
        env=git_identity_env,
    )

    assert commit_result.exit_code == 0, commit_result.stdout
    commit_payload = json.loads(commit_result.stdout)
    assert commit_payload["message"] == "feat: update readme"
    assert len(commit_payload["commit_hash"]) == 40

