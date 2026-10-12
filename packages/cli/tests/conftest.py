import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from pulseai.paths import ENGINE_DATA_ENV, engine_root
from pulseai.registry.loader import load_catalog
from pulseai.schemas import clear_schema_cache

REPO_ROOT = Path(__file__).resolve().parents[3]
ENGINE_DIRS = ("schema", "defaults", "taxonomy", "sources", "locales")


def _clear_caches() -> None:
    engine_root.cache_clear()
    load_catalog.cache_clear()
    clear_schema_cache()


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in list(os.environ):
        if name.startswith("PULSE__") or name == ENGINE_DATA_ENV:
            monkeypatch.delenv(name)
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture
def engine_copy(repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A writable copy of the engine data, selected through PULSE_ENGINE_DATA."""
    root = tmp_path / "engine"
    for name in ENGINE_DIRS:
        shutil.copytree(repo_root / name, root / name)
    monkeypatch.setenv(ENGINE_DATA_ENV, str(root))
    _clear_caches()
    return root
