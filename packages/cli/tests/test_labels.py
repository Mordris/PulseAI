import re
from pathlib import Path
from typing import Any

import pytest
import yaml

COLOR = re.compile(r"^[0-9a-f]{6}$")
# One flow mapping per line. PyYAML reads YAML 1.1, but the labeler action parses with a YAML 1.2
# library, where an unquoted 5319e7 is a number and an unquoted comma ends a value. Quoting every
# color and description makes both parsers return strings.
LABEL_LINE = re.compile(
    r'^- \{ name: (?:"[^"]+"|[^,:"{}]+), color: "[0-9a-f]{6}", description: "[^"]*" \}$'
)
KEPT_LABELS = {"autorelease: pending", "autorelease: tagged", "invalid"}


@pytest.fixture
def labels_file(repo_root: Path) -> Path:
    return repo_root / ".github" / "labels.yml"


@pytest.fixture
def labels(labels_file: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(labels_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def test_every_label_has_exactly_string_name_color_description(
    labels: list[dict[str, Any]],
) -> None:
    assert labels
    for label in labels:
        assert set(label) == {"name", "color", "description"}, label
        assert all(isinstance(value, str) and value for value in label.values()), label
        assert COLOR.match(label["color"]), label


def test_label_names_are_unique(labels: list[dict[str, Any]]) -> None:
    names = [label["name"] for label in labels]
    assert len(names) == len(set(names))


def test_raw_text_quotes_every_color_and_description(labels_file: Path) -> None:
    lines = [line for line in labels_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [line for line in lines if not LABEL_LINE.match(line)] == []


def test_labels_other_tools_depend_on_are_kept(labels: list[dict[str, Any]]) -> None:
    # The sync workflow deletes unlisted labels; release-please finds merged release pull requests
    # by "autorelease: pending", so losing it would stop tagging and publishing.
    assert {label["name"] for label in labels} >= KEPT_LABELS
