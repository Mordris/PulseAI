"""Apply GitHub repository settings from .github/repository.yml with the GitHub CLI.

Usage:
    uv run python scripts/github/apply_repo_settings.py --repo OWNER/NAME --dry-run
    uv run python scripts/github/apply_repo_settings.py --repo OWNER/NAME
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = ROOT / ".github" / "repository.yml"
SCHEMA_FILE = ROOT / ".github" / "repository.schema.json"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
API_HEADER = "Accept: application/vnd.github+json"
FieldValue = str | bool | int


class SettingsError(Exception):
    """repository.yml is missing or invalid."""


@dataclass(frozen=True)
class Call:
    method: str
    endpoint: str
    fields: tuple[tuple[str, FieldValue], ...] = ()
    body: dict[str, Any] | None = None

    def argv(self) -> list[str]:
        cmd = ["gh", "api", "-X", self.method, self.endpoint, "-H", API_HEADER]
        for key, value in self.fields:
            if isinstance(value, bool):
                cmd += ["-F", f"{key}={str(value).lower()}"]
            elif isinstance(value, int):
                cmd += ["-F", f"{key}={value}"]
            else:
                cmd += ["-f", f"{key}={value}"]
        if self.body is not None:
            cmd += ["--input", "-"]
        return cmd


def load_settings(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        msg = f"{path}: {exc}"
        raise SettingsError(msg) from None
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(data)
    )
    if errors:
        msg = f"{path}: invalid settings\n" + "\n".join(f"  - {e}" for e in errors)
        raise SettingsError(msg)
    settings: dict[str, Any] = data
    return settings


def _status(enabled: bool) -> str:
    return "enabled" if enabled else "disabled"


def build_calls(settings: dict[str, Any], repo: str) -> list[Call]:
    features, merge, security = settings["features"], settings["merge"], settings["security"]
    fields: list[tuple[str, FieldValue]] = [
        ("description", settings["description"].strip()),
        ("has_issues", features["issues"]),
        ("has_discussions", features["discussions"]),
        ("has_wiki", features["wiki"]),
        ("has_projects", features["projects"]),
        ("allow_squash_merge", merge["squash"]),
        ("allow_merge_commit", merge["merge_commit"]),
        ("allow_rebase_merge", merge["rebase"]),
        ("squash_merge_commit_title", merge["squash_title"]),
        ("squash_merge_commit_message", merge["squash_message"]),
        ("delete_branch_on_merge", merge["delete_branch_on_merge"]),
        ("allow_auto_merge", merge["auto_merge"]),
        ("security_and_analysis[secret_scanning][status]", _status(security["secret_scanning"])),
        (
            "security_and_analysis[secret_scanning_push_protection][status]",
            _status(security["push_protection"]),
        ),
    ]
    if settings["homepage"]:
        fields.append(("homepage", settings["homepage"]))
    return [
        Call("PATCH", f"repos/{repo}", tuple(fields)),
        Call("PUT", f"repos/{repo}/topics", tuple(("names[]", t) for t in settings["topics"])),
        Call(
            "PUT" if security["private_vulnerability_reporting"] else "DELETE",
            f"repos/{repo}/private-vulnerability-reporting",
        ),
        Call(
            "PUT" if security["dependabot_alerts"] else "DELETE",
            f"repos/{repo}/vulnerability-alerts",
        ),
    ]


def ruleset_body(settings: dict[str, Any]) -> dict[str, Any]:
    ruleset = settings["ruleset"]
    rules: list[dict[str, Any]] = [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": ruleset["required_approvals"],
                "dismiss_stale_reviews_on_push": ruleset["dismiss_stale_reviews_on_push"],
                "require_code_owner_review": ruleset["require_code_owner_review"],
                "require_last_push_approval": ruleset["require_last_push_approval"],
                "required_review_thread_resolution": ruleset["required_review_thread_resolution"],
            },
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": ruleset[
                    "strict_required_status_checks_policy"
                ],
                "required_status_checks": [{"context": c} for c in ruleset["required_checks"]],
            },
        },
    ]
    if ruleset["linear_history"]:
        rules.append({"type": "required_linear_history"})
    return {
        "name": ruleset["name"],
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": rules,
    }


def _run(call: Call) -> str:
    stdin = json.dumps(call.body) if call.body is not None else None
    result = subprocess.run(call.argv(), input=stdin, capture_output=True, text=True, check=True)
    return result.stdout


def _apply(call: Call) -> None:
    _run(call)
    print(f"applied {call.method} {call.endpoint}")


def _ruleset_call(repo: str, body: dict[str, Any]) -> Call:
    existing = json.loads(_run(Call("GET", f"repos/{repo}/rulesets")) or "[]")
    match = next((r for r in existing if r.get("name") == body["name"]), None)
    if match is None:
        return Call("POST", f"repos/{repo}/rulesets", body=body)
    return Call("PUT", f"repos/{repo}/rulesets/{match['id']}", body=body)


def _repo(value: str) -> str:
    if not REPO_PATTERN.match(value):
        msg = f"{value!r} is not OWNER/NAME"
        raise argparse.ArgumentTypeError(msg)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=_repo, help="OWNER/NAME")
    parser.add_argument("--dry-run", action="store_true", help="print the gh commands only")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(SETTINGS_FILE)
    except SettingsError as exc:
        print(exc, file=sys.stderr)
        return 2
    calls = build_calls(settings, args.repo)
    body = ruleset_body(settings)

    if args.dry_run:
        for call in calls:
            print(shlex.join(call.argv()))
        print(f"# then create or update ruleset {body['name']!r} via repos/{args.repo}/rulesets:")
        print(json.dumps(body, indent=2))
        return 0

    try:
        for call in calls:
            _apply(call)
        # The ruleset call depends on what already exists, so it is resolved last.
        _apply(_ruleset_call(args.repo, body))
    except subprocess.CalledProcessError as exc:
        command = exc.cmd if isinstance(exc.cmd, str) else shlex.join(str(a) for a in exc.cmd)
        print(f"error: {command} failed with exit status {exc.returncode}", file=sys.stderr)
        for stream in (exc.stderr, exc.output):
            if stream and str(stream).strip():
                print(str(stream).strip(), file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: could not run gh: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
