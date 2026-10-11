import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from pulseai.paths import ENGINE_DATA_ENV, engine_root

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in list(os.environ):
        if name.startswith("PULSE__") or name == ENGINE_DATA_ENV:
            monkeypatch.delenv(name)
    engine_root.cache_clear()
    yield
    engine_root.cache_clear()
