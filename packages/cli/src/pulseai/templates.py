"""Template fields in registry strings, such as `{date}` or `{config.window.max_hours}`.

The registry check validates them and the collector expands them, so both use this one reading of
what a field is and what a `config.*` field names.
"""

from __future__ import annotations

import string
from collections.abc import Iterator, Mapping
from typing import Any, NamedTuple, cast

# A template field `config.a.b` reads the config value at a.b.
CONFIG_VARIABLE_ROOT = "config"
CONFIG_VARIABLE_SEPARATOR = "."
# What a template field can expand to. bool is excluded: it is an int, but not a number to a human.
TEMPLATE_VALUE_TYPES = (str, int, float)

# What config_variable returns for a field that names no config value (None is a value).
MISSING = object()


class TemplatePart(NamedTuple):
    """Literal text, then the field that follows it (None after the last literal)."""

    literal: str
    field: str | None
    # The field carries a format spec or a conversion, as in {x:>5} or {x!r}.
    formatted: bool


def template_parts(text: str) -> Iterator[TemplatePart]:
    """A template split into literals and fields. Raises ValueError for unbalanced braces."""
    for literal, field, spec, conversion in string.Formatter().parse(text):
        yield TemplatePart(literal, field, formatted=bool(spec) or conversion is not None)


def field_problem(part: TemplatePart) -> str | None:
    """Why the part's field cannot be expanded, or None when it can (or there is no field).

    A field needs a name, and format specs and conversions are not supported.
    """
    if part.field == "":
        return "has no name"
    if part.formatted:
        return "has a format spec or conversion"
    return None


def config_variable(field: str, config: Mapping[str, Any]) -> object:
    """The config value a `config.<path>` template field names, or MISSING when there is none."""
    root, separator, path = field.partition(CONFIG_VARIABLE_SEPARATOR)
    if root != CONFIG_VARIABLE_ROOT or not separator:
        return MISSING
    value: object = config
    for key in path.split(CONFIG_VARIABLE_SEPARATOR):
        if not isinstance(value, dict):
            return MISSING
        children = cast("dict[str, object]", value)
        if key not in children:
            return MISSING
        value = children[key]
    return value


def is_template_value(value: object) -> bool:
    """Whether a template field can expand to this value: a string or a number, not a bool."""
    return isinstance(value, TEMPLATE_VALUE_TYPES) and not isinstance(value, bool)
