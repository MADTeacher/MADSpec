from __future__ import annotations

from typing import Any


def render_list(values: list[str]) -> list[str]:
    if not values:
        return ["- Пока не зафиксировано."]
    return [f"- {value}" for value in values]


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def schema_name(operation_id: str, suffix: str) -> str:
    parts = [segment for segment in operation_id.split("-") if segment]
    stem = "".join(part.capitalize() for part in parts) or "Operation"
    return f"{stem}{suffix}"


def render_architecture_markdown_document(
    normalized: dict[str, Any],
    *,
    branch_name: str,
    project_name: str = "",
) -> str:
    project_label = project_name or "Не указано"
    lines = [
        f"# Архитектура проекта: {project_label}",
        "",
        (
            f"**Основано на**: `.madspec/{branch_name}/memory/stages/mvp.architecture.json`, "
            f"`.madspec/{branch_name}/concept.md`, `.madspec/{branch_name}/ui-design.md`, `.madspec/{branch_name}/tech-stack.md`"
        ),
        "",
        "## Обзор",
        "",
        normalized["architectureOverview"] or "Пока не зафиксировано.",
        "",
        "## Структура проекта",
        "",
        f"- **Стратегия**: {normalized['projectStructure']['strategy'] or 'Не указано'}",
        f"- **Обоснование**: {normalized['projectStructure']['rationale'] or 'Не указано'}",
        "",
        "### Директории",
        "",
    ]
    if normalized["projectStructure"]["directories"]:
        for item in normalized["projectStructure"]["directories"]:
            lines.append(f"- `{item['path']}`: {item['purpose']}")
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(
        [
            "",
            "## Модель данных",
            "",
            f"**Детальная модель**: `.madspec/{branch_name}/data-model.md`",
            "",
        ]
    )
    for entity in normalized["dataModel"]["entities"]:
        lines.extend(
            [
                f"### {entity['name']}",
                "",
                entity.get("description") or "Без описания.",
                "",
                f"- Полей: {len(entity.get('fields', []))}",
                f"- Связей: {len(entity.get('relationships', []))}",
                f"- Состояний: {len(entity.get('states', []))}",
                "",
            ]
        )
    if not normalized["dataModel"]["entities"]:
        lines.extend(["Пока не зафиксировано.", ""])
    lines.extend(
        [
            "## API контракты",
            "",
            f"- **API style**: `{normalized['contracts']['apiStyle']}`",
            f"- **OpenAPI**: `.madspec/{branch_name}/contracts/openapi.yaml`",
            f"- **Endpoints**: {len(normalized['contracts']['endpoints'])}",
            "",
        ]
    )
    for endpoint in normalized["contracts"]["endpoints"]:
        lines.append(f"- `{endpoint['method']} {endpoint['path']}` (`{endpoint['operationId']}`) - {endpoint['summary']}")
    if not normalized["contracts"]["endpoints"]:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "## Внешние интеграции", ""])
    if normalized["integrations"]:
        for integration in normalized["integrations"]:
            touchpoints = ", ".join(integration.get("touchpoints", [])) or "Не указано"
            lines.append(
                f"- **{integration['name']}** ({integration['kind']}): {integration['purpose']} | Touchpoints: {touchpoints}"
            )
    else:
        lines.append("- Пока не зафиксировано.")
    lines.extend(["", "## Принципы организации кода", "", *render_list(normalized["codePrinciples"]), ""])
    lines.extend(["## Архитектурные паттерны", ""])
    if normalized["patterns"]:
        for item in normalized["patterns"]:
            lines.append(f"- **{item['name']}**: {item['rationale']}")
        lines.append("")
    else:
        lines.extend(["- Пока не зафиксировано.", ""])
    lines.extend(["## Безопасность", "", *render_list(normalized["securityNotes"]), ""])
    lines.extend(["## Производительность", "", *render_list(normalized["performanceNotes"]), ""])
    lines.extend(["## Следующие шаги", "", *render_list(normalized["nextActions"]), ""])
    lines.extend(
        [
            "## Checkpoint",
            "",
            normalized["checkpointSummary"] or "Пока не зафиксировано.",
            "",
            (
                f"Версия: {normalized['revision']} | "
                f"Ратифицирована: {normalized['ratifiedAt'] or 'Не указано'} | "
                f"Последнее изменение: {normalized['updatedAt'] or 'Не указано'}"
            ),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def render_data_model_markdown_document(
    normalized: dict[str, Any],
    *,
    branch_name: str,
    project_name: str = "",
) -> str:
    project_label = project_name or "Не указано"
    lines = [
        f"# Модель данных: {project_label}",
        "",
        f"**Основано на**: `.madspec/{branch_name}/memory/stages/mvp.architecture.json`",
        "",
    ]
    if not normalized["dataModel"]["entities"]:
        lines.extend(["Пока не зафиксировано.", ""])
        return "\n".join(lines) + "\n"
    for entity in normalized["dataModel"]["entities"]:
        lines.extend([f"## {entity['name']}", "", entity.get("description") or "Без описания.", "", "### Поля", ""])
        if entity.get("fields"):
            for field in entity["fields"]:
                required = "required" if field.get("required") else "optional"
                lines.append(
                    f"- **{field['name']}** `{field['type']}` ({required}) - {field.get('description') or 'Без описания'}"
                )
        else:
            lines.append("- Пока не зафиксировано.")
        lines.extend(["", "### Связи", ""])
        if entity.get("relationships"):
            for relation in entity["relationships"]:
                lines.append(f"- **{relation['kind']}** -> `{relation['target']}`: {relation['description']}")
        else:
            lines.append("- Пока не зафиксировано.")
        lines.extend(["", "### Состояния", ""])
        if entity.get("states"):
            for item in entity["states"]:
                lines.append(f"- **{item['name']}**: {item['description']}")
        else:
            lines.append("- Пока не зафиксировано.")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_object_schema(name: str, fields: list[dict[str, Any]], *, indent: str) -> list[str]:
    lines = [f"{indent}{name}:", f"{indent}  type: object", f"{indent}  properties:"]
    required_names = [field["name"] for field in fields if field.get("required")]
    for field in fields:
        lines.extend(
            [
                f"{indent}    {field['name']}:",
                f"{indent}      type: {yaml_quote(field['type'])}",
                f"{indent}      description: {yaml_quote(field.get('description') or '')}",
            ]
        )
    if required_names:
        lines.append(f"{indent}  required:")
        for field_name in required_names:
            lines.append(f"{indent}    - {field_name}")
    return lines


def render_openapi_yaml_document(normalized: dict[str, Any], *, branch_name: str) -> str:
    lines = [
        "openapi: 3.0.3",
        "info:",
        f"  title: {yaml_quote(f'MADSpec {branch_name} Architecture API')}",
        '  version: "1.0.0"',
        "paths:",
    ]
    endpoints = sorted(
        normalized["contracts"]["endpoints"],
        key=lambda item: (item.get("path", ""), item.get("method", ""), item.get("operationId", "")),
    )
    if not endpoints:
        lines.append("  {}")
    else:
        for endpoint in endpoints:
            lines.append(f"  {endpoint['path']}:")
            lines.append(f"    {endpoint['method'].lower()}:")
            lines.append(f"      operationId: {endpoint['operationId']}")
            lines.append(f"      summary: {yaml_quote(endpoint['summary'])}")
            if endpoint.get("screenIds"):
                lines.append("      tags:")
                for screen_id in endpoint["screenIds"]:
                    lines.append(f"        - {yaml_quote(screen_id)}")
            parameter_fields = [field for field in endpoint.get("fields", []) if field.get("section") in {"path", "query"}]
            if parameter_fields:
                lines.append("      parameters:")
                for field in parameter_fields:
                    lines.extend(
                        [
                            f"        - name: {field['name']}",
                            f"          in: {field['section']}",
                            f"          required: {'true' if field.get('required') else 'false'}",
                            "          schema:",
                            f"            type: {yaml_quote(field['type'])}",
                            f"          description: {yaml_quote(field.get('description') or '')}",
                        ]
                    )
            request_fields = [field for field in endpoint.get("fields", []) if field.get("section") == "request"]
            if request_fields:
                request_schema = schema_name(endpoint["operationId"], "Request")
                lines.extend(
                    [
                        "      requestBody:",
                        "        required: true",
                        "        content:",
                        "          application/json:",
                        "            schema:",
                        f"              $ref: '#/components/schemas/{request_schema}'",
                    ]
                )
            lines.append("      responses:")
            response_fields = [field for field in endpoint.get("fields", []) if str(field.get("section", "")).startswith("response:")]
            grouped_responses: dict[str, list[dict[str, Any]]] = {}
            for field in response_fields:
                status = field["section"].split(":", 1)[1]
                grouped_responses.setdefault(status, []).append(field)
            error_lookup = {error["status"]: error for error in endpoint.get("errors", [])}
            if not grouped_responses:
                lines.extend(['        "200":', "          description: OK"])
            else:
                for status in sorted(grouped_responses):
                    response_schema = schema_name(endpoint["operationId"], f"{status}Response")
                    description = error_lookup.get(status, {}).get("description", "Success")
                    lines.extend(
                        [
                            f'        "{status}":',
                            f"          description: {yaml_quote(description)}",
                            "          content:",
                            "            application/json:",
                            "              schema:",
                            f"                $ref: '#/components/schemas/{response_schema}'",
                        ]
                    )
    lines.append("components:")
    lines.append("  schemas:")
    emitted_schemas = False
    for endpoint in endpoints:
        request_fields = [field for field in endpoint.get("fields", []) if field.get("section") == "request"]
        if request_fields:
            emitted_schemas = True
            request_schema = schema_name(endpoint["operationId"], "Request")
            lines.extend(render_object_schema(request_schema, request_fields, indent="    "))
        response_fields = [field for field in endpoint.get("fields", []) if str(field.get("section", "")).startswith("response:")]
        grouped_responses: dict[str, list[dict[str, Any]]] = {}
        for field in response_fields:
            status = field["section"].split(":", 1)[1]
            grouped_responses.setdefault(status, []).append(field)
        for status in sorted(grouped_responses):
            emitted_schemas = True
            response_schema = schema_name(endpoint["operationId"], f"{status}Response")
            lines.extend(render_object_schema(response_schema, grouped_responses[status], indent="    "))
    if not emitted_schemas:
        lines.append("    EmptyObject:")
        lines.append("      type: object")
        lines.append("      properties: {}")
    return "\n".join(lines) + "\n"
