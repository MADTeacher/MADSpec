from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontmatter_profiles import subagent_frontmatter_profile_for_environment


TOOL_POLICY_KEYS = ("read", "search", "edit", "write", "bash")


@dataclass(frozen=True)
class ToolTranslator:
    translator_id: str
    output_format: str
    mapping: tuple[tuple[str, str], ...]
    ignored_sources: tuple[str, ...] = ()


TOOL_TRANSLATORS = {
    "opencode-tools-v1": ToolTranslator(
        translator_id="opencode-tools-v1",
        output_format="mapping",
        mapping=(
            ("edit", "edit"),
            ("write", "write"),
            ("bash", "bash"),
        ),
        ignored_sources=("read", "search"),
    ),
    "qwen-tools-v1": ToolTranslator(
        translator_id="qwen-tools-v1",
        output_format="list",
        mapping=(
            ("read", "read_file"),
            ("search", "glob"),
            ("search", "grep_search"),
            ("edit", "edit"),
            ("write", "write_file"),
            ("bash", "run_shell_command"),
        ),
    ),
    "copilot-tools-v1": ToolTranslator(
        translator_id="copilot-tools-v1",
        output_format="list",
        mapping=(
            ("read", "read"),
            ("search", "search"),
            ("edit", "edit"),
            ("write", "edit"),
            ("bash", "terminal"),
        ),
    ),
}


def translate_tool_policy(environment_id: str, tool_policy: dict[str, Any]) -> dict[str, bool] | list[str] | None:
    profile = subagent_frontmatter_profile_for_environment(environment_id)
    translator_id = profile.tool_translator_id
    if translator_id is None:
        return None
    try:
        translator = TOOL_TRANSLATORS[translator_id]
    except KeyError as exc:
        raise ValueError(f"Unknown tool translator for {environment_id}: {translator_id}") from exc

    generic_keys = set(tool_policy)
    allowed_generic_keys = {source for source, _ in translator.mapping} | set(translator.ignored_sources)
    unexpected_keys = generic_keys - allowed_generic_keys
    if unexpected_keys:
        raise ValueError(
            f"Unsupported tool policy keys for {environment_id}: {', '.join(sorted(unexpected_keys))}"
        )

    if translator.output_format == "mapping":
        translated: dict[str, bool] = {}
        for source, target in translator.mapping:
            translated[target] = bool(tool_policy.get(source, False))
        return translated
    if translator.output_format == "list":
        translated_list: list[str] = []
        for source, target in translator.mapping:
            if bool(tool_policy.get(source, False)) and target not in translated_list:
                translated_list.append(target)
        return translated_list
    raise ValueError(f"Unsupported tool translator output format: {translator.output_format}")
