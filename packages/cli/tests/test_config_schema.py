import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator


def _validator(root: Path) -> Draft202012Validator:
    schema = json.loads((root / "schema/config.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def _defaults(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "defaults/pulse.config.yaml").read_text(encoding="utf-8"))


def test_defaults_validate(repo_root: Path) -> None:
    assert list(_validator(repo_root).iter_errors(_defaults(repo_root))) == []


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schedule", "time"), "25:00"),
        (("language",), "english"),
        (("theme", "default"), "sepia"),
        (("publish", "repo"), "not a repo"),
        (("theme", "overrides", "accent"), "blue"),
        (("limits", "run_minutes"), 0),
    ],
)
def test_rejects_bad_values(repo_root: Path, path: tuple[str, ...], value: object) -> None:
    data = _defaults(repo_root)
    target = data
    for key in path[:-1]:
        target = target.setdefault(key, {})
    target[path[-1]] = value
    assert list(_validator(repo_root).iter_errors(data))


def test_rejects_unknown_keys(repo_root: Path) -> None:
    data = _defaults(repo_root)
    data["schedul"] = {}
    assert list(_validator(repo_root).iter_errors(data))


def test_generated_model_parses_defaults(repo_root: Path) -> None:
    from pulseai.models.config import PulseConfig

    cfg = PulseConfig.model_validate(_defaults(repo_root))
    assert cfg.schedule.time == "17:00"
    assert cfg.schedule.tz == "Europe/Istanbul"
    assert cfg.models_by_role["editor"] == "claude-opus-5-5"


@pytest.mark.slow
def test_generated_models_are_up_to_date(repo_root: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts/generate_models.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    assert result.returncode == 0, result.stderr
