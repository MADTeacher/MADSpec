from __future__ import annotations

from madspec_cli.shared.cli.toon_output import encode_toon


def test_encode_toon_renders_nested_payload_with_tabular_arrays() -> None:
    payload = {
        "branch": "main",
        "valid": False,
        "items": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ],
        "mixed": ["one", {"nested": True}],
    }

    rendered = encode_toon(payload)

    assert "branch: main" in rendered
    assert "valid: false" in rendered
    assert "items[2,]{id,name}:" in rendered
    assert "  1,Alice" in rendered
    assert "mixed:" in rendered
    assert "  [2]:" in rendered
    assert "    - one" in rendered
    assert "    - nested: true" in rendered


def test_encode_toon_quotes_strings_that_would_be_ambiguous() -> None:
    payload = {"null_like": "null", "csv": "a,b", "spaced": "  value  "}

    rendered = encode_toon(payload)

    assert 'null_like: "null"' in rendered
    assert 'csv: "a,b"' in rendered
    assert 'spaced: "  value  "' in rendered
