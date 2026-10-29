"""Template fields in registry strings, such as `{date}` or `{config.window.max_hours}`.

The registry check validates them and the collector expands them, so both use this one reading of
what a field is and what a `config.*` field names.
"""

from __future__ import annotations

import string
from collections.abc import Iterator, Mapping
from typing import Any, cast

# A template field `config.a.b` reads the config value at a.b.
CONFIG_VARIABLE_ROOT = "config"
CONFIG_VARIABLE_SEPARATOR = "."
# What a template field can expand to. bool is excluded: it is an int, but not a number to a human.
TEMPLATE_VALUE_TYPES = (str, int, float)

# What config_variable returns for a field that names no config value (None is a value).
MISSING = object()


def template_fields(text: str) -> Iterator[str]:
    """The named fields of a template, in order. Raises ValueError for unbalanced braces."""
    for _, field, _, _ in string.Formatter().parse(text):
        if field:
            yield field


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
