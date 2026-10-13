"""Design-token gate: text contrast and distinguishable colors in every theme mode.

Reads the resolved token maps @pulseai/tokens writes (<instance>/.pulse/tokens/<mode>.json), the
sections registry (each section's color token), and the thresholds in config.quality. Values come
from those files; this module holds only the rules.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from coloraide import Color

from pulseai.config import load_config
from pulseai.issues import Issue, unusable_issue
from pulseai.models.config import PulseConfig
from pulseai.registry.loader import load_registry
from pulseai.schemas import SCHEMA_PROBLEMS, load_schema, validate_document
from pulseai.site.context import WORK_DIR

RESOLVED_SCHEMA = "tokens-resolved.schema.json"
TOKENS_DIR = "tokens"
SECTION_SET = "sections"
# WCAG 2.1 contrast ratio; OKLab delta E scaled by 100, the unit of the config.quality thresholds.
CONTRAST_METHOD = "wcag21"
DELTA_E_METHOD = "ok"
DELTA_E_SCALE = 100

Member = tuple[str, Any]
Pair = tuple[Member, Member]


class TokenFileError(Exception):
    """A resolved token map is missing, unreadable, or not a resolved token map."""


def default_tokens_dir(instance_dir: Path | None) -> Path:
    return (instance_dir or Path.cwd()) / WORK_DIR / TOKENS_DIR


def _error(where: str, message: str) -> Issue:
    return Issue("error", where, message)


def _modes() -> list[str]:
    try:
        schema = load_schema(RESOLVED_SCHEMA)
    except SCHEMA_PROBLEMS as exc:
        msg = f"cannot use schema {RESOLVED_SCHEMA!r} ({exc})"
        raise TokenFileError(msg) from None
    return list(schema["properties"]["mode"]["enum"])


def _read(path: Path, mode: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        msg = f"{path}: not found; build the site first (it writes the token maps) or pass --tokens"
        raise TokenFileError(msg) from None
    except OSError as exc:
        msg = f"{path}: cannot read ({exc.strerror or type(exc).__name__})"
        raise TokenFileError(msg) from None
    try:
        data: Any = json.loads(text)
    except ValueError as exc:
        msg = f"{path}: {exc}"
        raise TokenFileError(msg) from None
    try:
        errors = validate_document(data, RESOLVED_SCHEMA)
    except SCHEMA_PROBLEMS as exc:
        msg = f"cannot use schema {RESOLVED_SCHEMA!r} ({exc})"
        raise TokenFileError(msg) from None
    if errors:
        lines = "\n".join(f"  - {error}" for error in errors)
        msg = f"{path}: not a resolved token map\n{lines}"
        raise TokenFileError(msg)
    if data["mode"] != mode:
        msg = f"{path}: holds the {data['mode']!r} mode, expected {mode!r}"
        raise TokenFileError(msg)
    return data


def _color(value: Any) -> Color | None:
    if not isinstance(value, str):
        return None
    try:
        return Color(value)
    except ValueError:
        return None


def _delta(a: Color, b: Color, simulation: str | None = None) -> float:
    if simulation is not None:
        a, b = a.filter(simulation), b.filter(simulation)
    return a.delta_e(b, method=DELTA_E_METHOD, scalar=DELTA_E_SCALE)


def _check_contrast(mode: str, tokens: dict[str, Any], cfg: PulseConfig) -> Iterator[Issue]:
    minimum = cfg.quality.text_contrast_min
    for path, token in tokens.items():
        for target in token.get("extensions", {}).get("contrast_against", []):
            where = f"{mode}/{path}"
            other = tokens.get(target)
            if other is None:
                yield _error(where, f"contrast target {target!r} is not defined")
                continue
            fg, bg = _color(token["value"]), _color(other["value"])
            if fg is None or bg is None:
                yield _error(where, f"cannot compare {token['value']!r} with {target}: not a color")
                continue
            ratio = fg.contrast(bg, method=CONTRAST_METHOD)
            if ratio < minimum:
                yield _error(where, f"contrast {ratio:.2f}:1 against {target} is below {minimum}:1")


def _check_pairs(mode: str, name: str, pairs: list[Pair], cfg: PulseConfig) -> Iterator[Issue]:
    quality = cfg.quality
    where = f"{mode}/{name}"
    for (a_path, a_value), (b_path, b_value) in pairs:
        a, b = _color(a_value), _color(b_value)
        if a is None or b is None:
            yield _error(where, f"{a_path} and {b_path} must both be colors")
            continue
        normal = _delta(a, b)
        if normal < quality.section_delta_e_min:
            yield _error(
                where,
                f"{a_path} and {b_path} are too similar "
                f"(delta E {normal:.1f}, minimum {quality.section_delta_e_min})",
            )
        for simulation in quality.cvd_simulations:
            simulated = _delta(a, b, simulation)
            if simulated < quality.section_cvd_fail:
                yield _error(
                    where,
                    f"{a_path} and {b_path} are too similar under {simulation} simulation "
                    f"(delta E {simulated:.1f}, minimum {quality.section_cvd_fail})",
                )
            elif simulated < quality.section_cvd_target:
                yield Issue(
                    "warning",
                    where,
                    f"{a_path} and {b_path} are close under {simulation} simulation "
                    f"(delta E {simulated:.1f}, target {quality.section_cvd_target}); "
                    "pair them with labels or patterns",
                )


def _declared_sets(tokens: dict[str, Any]) -> dict[str, list[tuple[int | None, str, Any]]]:
    sets: dict[str, list[tuple[int | None, str, Any]]] = {}
    for path, token in tokens.items():
        distinct = token.get("extensions", {}).get("distinct")
        if distinct is not None:
            member = (distinct.get("order"), path, token["value"])
            sets.setdefault(distinct["set"], []).append(member)
    return sets


def _set_pairs(members: list[tuple[int | None, str, Any]]) -> list[Pair]:
    """Neighbours when every member has an order (a categorical sequence), else every pair."""
    orders = [order for order, _, _ in members]
    if all(order is not None for order in orders):
        ordered = sorted(members, key=lambda member: member[0] or 0)
        return [((a[1], a[2]), (b[1], b[2])) for a, b in itertools.pairwise(ordered)]
    plain = [(path, value) for _, path, value in members]
    return list(itertools.combinations(plain, 2))


def _check_mode(
    mode: str, tokens: dict[str, Any], sections: list[dict[str, Any]], cfg: PulseConfig
) -> Iterator[Issue]:
    yield from _check_contrast(mode, tokens, cfg)
    members: list[Member] = []
    for section in sections:
        token = tokens.get(section["color_token"])
        if token is None:
            yield _error(
                f"{mode}/{SECTION_SET}",
                f"section {section['id']!r} color token {section['color_token']!r} is not defined",
            )
        else:
            members.append((section["color_token"], token["value"]))
    yield from _check_pairs(mode, SECTION_SET, list(itertools.combinations(members, 2)), cfg)
    for name, declared in sorted(_declared_sets(tokens).items()):
        yield from _check_pairs(mode, name, _set_pairs(declared), cfg)


def check_tokens(tokens_dir: Path, instance_dir: Path | None = None) -> list[Issue]:
    """Every contrast and distinctness problem in the resolved token maps under tokens_dir."""
    cfg = load_config(instance_dir)
    sections = load_registry("sections", instance_dir).data["sections"]
    issues: list[Issue] = []
    try:
        maps = {mode: _read(tokens_dir / f"{mode}.json", mode) for mode in _modes()}
    except TokenFileError as exc:
        return [unusable_issue("tokens", str(exc))]
    for mode, doc in maps.items():
        issues += _check_mode(mode, doc["tokens"], sections, cfg)
    return sorted(issues)
