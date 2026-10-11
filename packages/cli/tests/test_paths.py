import subprocess
import zipfile
from pathlib import Path

import pytest

from pulseai import paths
from pulseai.paths import ENGINE_DATA_ENV, EngineDataError, data_path, engine_root


def test_engine_root_is_repo_root_in_a_checkout(repo_root: Path) -> None:
    assert engine_root() == repo_root
    assert data_path("schema", "config.schema.json").is_file()


def test_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "schema").mkdir()
    (tmp_path / "schema" / "config.schema.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv(ENGINE_DATA_ENV, str(tmp_path))
    assert engine_root() == tmp_path.resolve()


def test_bad_override_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENGINE_DATA_ENV, str(tmp_path))
    with pytest.raises(EngineDataError, match="does not contain"):
        engine_root()


def test_packaged_data_used_outside_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packaged = tmp_path / "_data"
    (packaged / "schema").mkdir(parents=True)
    (packaged / "schema" / "config.schema.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths, "_checkout_root", lambda: None)
    monkeypatch.setattr(paths, "_packaged_data_dir", lambda: packaged)
    assert engine_root() == packaged


def test_checkout_wins_over_packaged_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    checkout = tmp_path / "checkout"
    packaged = tmp_path / "_data"
    for root in (checkout, packaged):
        (root / "schema").mkdir(parents=True)
        (root / "schema" / "config.schema.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paths, "_checkout_root", lambda: checkout)
    monkeypatch.setattr(paths, "_packaged_data_dir", lambda: packaged)
    assert engine_root() == checkout


def test_checkout_root_found_for_the_repository_layout(tmp_path: Path) -> None:
    package_dir = tmp_path / "packages" / "cli" / "src" / "pulseai"
    package_dir.mkdir(parents=True)
    (tmp_path / "schema").mkdir()
    (tmp_path / "schema" / "config.schema.json").write_text("{}", encoding="utf-8")
    assert paths._checkout_root(package_dir) == tmp_path.resolve()


def test_checkout_root_ignores_a_stray_marker_above_an_installed_package(tmp_path: Path) -> None:
    (tmp_path / "schema").mkdir()
    (tmp_path / "schema" / "config.schema.json").write_text("{}", encoding="utf-8")
    installed = tmp_path / "venv" / "lib" / "site-packages" / "pulseai"
    installed.mkdir(parents=True)
    assert paths._checkout_root(installed) is None


def test_no_data_anywhere_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "_checkout_root", lambda: None)
    monkeypatch.setattr(paths, "_packaged_data_dir", lambda: tmp_path / "missing")
    with pytest.raises(EngineDataError, match="engine data not found"):
        engine_root()


@pytest.mark.slow
def test_wheel_bundles_engine_data(repo_root: Path, tmp_path: Path) -> None:
    try:
        subprocess.run(
            ["uv", "build", "--wheel", "--package", "pulseai", "--out-dir", str(tmp_path)],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        pytest.fail(f"uv build failed:\n{exc.stderr}")
    wheel = next(tmp_path.glob("pulseai-*.whl"))
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
    for rel in (
        "schema/config.schema.json",
        "schema/item-types/paper.schema.json",
        "defaults/pulse.config.yaml",
        "defaults/registries.yaml",
        "taxonomy/sections.yaml",
        "sources/registry/core.yaml",
        "locales/en.json",
    ):
        assert f"pulseai/_data/{rel}" in names
