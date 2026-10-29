import pytest

from pulseai.templates import (
    MISSING,
    TemplatePart,
    config_variable,
    is_template_value,
    template_fields,
    template_parts,
)

CONFIG = {"window": {"max_hours": 72}, "name": "x", "deep": {"a": {"b": 1.5}}, "flag": True}


def test_template_fields_lists_named_fields_in_order() -> None:
    assert list(template_fields("https://x/{date}/{config.window.max_hours}?q={until}")) == [
        "date",
        "config.window.max_hours",
        "until",
    ]


def test_template_fields_skips_literals_escaped_braces_and_empty_fields() -> None:
    assert list(template_fields("plain {{literal}} {} text")) == []


def test_template_parts_split_a_template_into_literals_and_fields() -> None:
    parts = list(template_parts("a/{date}/b{{c}}/{config.x}"))
    assert "".join(part.literal for part in parts) == "a//b{c}/"
    assert [part.field for part in parts if part.field is not None] == ["date", "config.x"]
    assert parts[0] == TemplatePart("a/", "date", formatted=False)


def test_template_parts_keeps_trailing_literals_and_empty_fields() -> None:
    assert list(template_parts("{date}/tail")) == [
        TemplatePart("", "date", formatted=False),
        TemplatePart("/tail", None, formatted=False),
    ]
    assert list(template_parts("x{}")) == [TemplatePart("x", "", formatted=False)]


@pytest.mark.parametrize("text", ["{date:%Y}", "{date!r}", "{date!s:>5}"])
def test_template_parts_flags_format_specs_and_conversions(text: str) -> None:
    assert [part.formatted for part in template_parts(text)] == [True]


def test_template_parts_does_not_flag_plain_fields() -> None:
    assert [part.formatted for part in template_parts("{date}{config.a.b}")] == [False, False]


@pytest.mark.parametrize("text", ["https://x/{date", "https://x/date}"])
def test_template_fields_rejects_unbalanced_braces(text: str) -> None:
    with pytest.raises(ValueError, match="}"):
        list(template_fields(text))


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("config.name", "x"),
        ("config.window.max_hours", 72),
        ("config.deep.a.b", 1.5),
        ("config.window", {"max_hours": 72}),
    ],
)
def test_config_variable_reads_dotted_paths(field: str, expected: object) -> None:
    assert config_variable(field, CONFIG) == expected


@pytest.mark.parametrize(
    "field",
    [
        "date",  # not under the config root
        "config",  # the root alone names no value
        "other.name",
        "config.missing",
        "config.window.missing",
        "config.name.deeper",  # name is a string, not a table
        "config..name",
        "config.",
    ],
)
def test_config_variable_is_missing_for_anything_else(field: str) -> None:
    assert config_variable(field, CONFIG) is MISSING


@pytest.mark.parametrize("value", ["text", "", 0, 72, 1.5])
def test_scalars_are_template_values(value: object) -> None:
    assert is_template_value(value)


@pytest.mark.parametrize("value", [True, False, None, [1], {"a": 1}, ("a",), b"x"])
def test_booleans_and_non_scalars_are_not_template_values(value: object) -> None:
    assert not is_template_value(value)
