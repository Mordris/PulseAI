"""A validation finding shared by every checker."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Level = Literal["error", "warning"]


@dataclass(frozen=True, order=True)
class Issue:
    level: Level
    where: str
    message: str


def has_errors(issues: Iterable[Issue]) -> bool:
    return any(issue.level == "error" for issue in issues)


def format_issue(issue: Issue) -> str:
    return f"{issue.level} {issue.where}: {issue.message}"
