"""A validation finding shared by every checker."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Level = Literal["error", "warning"]


@dataclass(frozen=True, order=True)
class Issue:
    """One finding. `unusable` marks input that could not be loaded at all (engine data, catalog,
    config, registries, or an unreadable file), as opposed to a problem found in loaded data."""

    level: Level
    where: str
    message: str
    unusable: bool = False


def unusable_issue(where: str, message: str) -> Issue:
    return Issue("error", where, message, unusable=True)


def is_unusable(issues: Iterable[Issue]) -> bool:
    return any(issue.unusable for issue in issues)


def has_errors(issues: Iterable[Issue]) -> bool:
    return any(issue.level == "error" for issue in issues)


def format_issue(issue: Issue) -> str:
    return f"{issue.level} {issue.where}: {issue.message}"
