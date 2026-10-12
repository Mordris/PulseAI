from pathlib import Path
from typing import Any

from token_fixtures import entry, passing, write
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.issues import Issue, is_unusable
from pulseai.tokens.check import check_tokens, default_tokens_dir

runner = CliRunner()


def _messages(issues: list[Issue], level: str = "error") -> list[str]:
    return [f"{i.where}: {i.message}" for i in issues if i.level == level]


def _with(mode: str, **values: Any) -> dict[str, Any]:
    doc = passing(mode)
    for path, value in values.items():
        doc["tokens"][path.replace("__", ".")]["value"] = value
    return doc


def test_a_passing_theme_has_no_issues(tmp_path: Path) -> None:
    assert check_tokens(write(tmp_path)) == []


def test_default_tokens_dir_is_in_the_work_dir(tmp_path: Path) -> None:
    assert default_tokens_dir(tmp_path) == tmp_path / ".pulse" / "tokens"


def test_low_text_contrast_is_an_error(tmp_path: Path) -> None:
    doc = _with("light", color__text__primary="#9a9a9a")
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert messages == [
        "light/color.text.primary: contrast 2.81:1 against color.surface.page is below 4.5:1"
    ]


def test_a_missing_contrast_target_is_an_error(tmp_path: Path) -> None:
    doc = passing("dark")
    del doc["tokens"]["color.surface.page"]
    messages = _messages(check_tokens(write(tmp_path, {"dark": doc})))
    assert (
        "dark/color.text.primary: contrast target 'color.surface.page' is not defined" in messages
    )


def test_similar_section_colors_are_an_error(tmp_path: Path) -> None:
    doc = _with("light", color__section__tooling="#2f7fd9")
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert any(
        m.startswith(
            "light/sections: color.section.models and color.section.tooling are too similar"
        )
        for m in messages
    ), messages


def test_a_section_without_a_color_token_is_an_error(tmp_path: Path) -> None:
    doc = passing("light")
    del doc["tokens"]["color.section.oss"]
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert (
        "light/sections: section 'oss' color token 'color.section.oss' is not defined" in messages
    )


def test_colors_that_collapse_under_a_cvd_simulation_are_an_error(tmp_path: Path) -> None:
    doc = _with("light", color__chart__category__1="#d03b3b", color__chart__category__2="#5f8f00")
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert any("under deutan simulation" in m for m in messages), messages


def test_colors_in_the_cvd_warning_band_are_a_warning(tmp_path: Path) -> None:
    doc = _with("light", color__chart__category__1="#1baf7a", color__chart__category__2="#e34948")
    issues = check_tokens(write(tmp_path, {"light": doc}))
    assert _messages(issues) == []
    assert any("pair them with labels or patterns" in m for m in _messages(issues, "warning"))


def test_an_ordered_set_compares_neighbours_only(tmp_path: Path) -> None:
    # Slots 1 and 3 are identical, but only neighbours are ever on screen together.
    doc = _with("light", color__chart__category__3="#2a78d6")
    assert check_tokens(write(tmp_path, {"light": doc})) == []
    del doc["tokens"]["color.chart.category.3"]["extensions"]["distinct"]["order"]
    messages = _messages(check_tokens(write(tmp_path, {"light": doc})))
    assert any("color.chart.category.1 and color.chart.category.3" in m for m in messages)


def test_cvd_simulations_come_from_the_config(tmp_path: Path) -> None:
    instance = tmp_path / "instance"
    instance.mkdir()
    (instance / "pulse.config.yaml").write_text(
        "quality:\n  cvd_simulations: [protan]\n", encoding="utf-8"
    )
    doc = _with(
        "light",
        color__chart__category__1="#d03b3b",
        color__chart__category__2="#5f8f00",
        color__chart__category__3="#4a3aa7",
    )
    assert check_tokens(write(tmp_path / "tokens", {"light": doc}), instance) == []


def test_a_missing_token_map_is_unusable(tmp_path: Path) -> None:
    issues = check_tokens(tmp_path / "nowhere")
    assert is_unusable(issues)
    assert "light.json: not found; build the site first" in issues[0].message


def test_a_map_that_fails_its_schema_is_unusable(tmp_path: Path) -> None:
    doc = passing("light")
    doc["tokens"]["color.surface.page"]["name"] = "not-a-css-variable"
    issues = check_tokens(write(tmp_path, {"light": doc}))
    assert is_unusable(issues)
    assert "not a resolved token map" in issues[0].message


def test_a_map_for_the_wrong_mode_is_unusable(tmp_path: Path) -> None:
    issues = check_tokens(write(tmp_path, {"light": passing("dark")}))
    assert is_unusable(issues)
    assert "holds the 'dark' mode, expected 'light'" in issues[0].message


def test_cli_passes_and_fails(tmp_path: Path) -> None:
    good = write(tmp_path / "good")
    result = runner.invoke(app, ["tokens", "check", "--tokens", str(good)])
    assert result.exit_code == 0, result.output
    assert "Design tokens pass." in result.stdout
    bad = write(tmp_path / "bad", {"dark": _with("dark", color__text__primary="#222222")})
    result = runner.invoke(app, ["tokens", "check", "--tokens", str(bad)])
    assert result.exit_code == 1
    assert "dark/color.text.primary: contrast" in result.stderr


def test_entry_names_follow_the_css_prefix() -> None:
    assert entry("color.text.primary", "#000000")["name"] == "--pulse-color-text-primary"
