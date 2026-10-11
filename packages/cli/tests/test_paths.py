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


def test_no_data_anywhere_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "_checkout_root", lambda: None)
    monkeypatch.setattr(paths, "_packaged_data_dir", lambda: tmp_path / "missing")
    with pytest.raises(EngineDataError, match="engine data not found"):
        engine_root()


@pytest.mark.slow
def test_wheel_bundles_engine_data(repo_root: Path, tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--package", "pulseai", "--out-dir", str(tmp_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    wheel = next(tmp_path.glob("pulseai-*.whl"))
    names = set(zipfile.ZipFile(wheel).namelist())
    for rel in ("schema/config.schema.json", "defaults/pulse.config.yaml"):
        assert f"pulseai/_data/{rel}" in names
