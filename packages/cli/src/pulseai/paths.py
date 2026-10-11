"""Locate engine data (schemas, registries, defaults) in installed wheels and source checkouts."""

from __future__ import annotations

import os
from functools import cache
from importlib.resources import files
from pathlib import Path

ENGINE_DATA_ENV = "PULSE_ENGINE_DATA"
MARKER = Path("schema") / "config.schema.json"


class EngineDataError(RuntimeError):
    """Engine data could not be located."""


def _checkout_root() -> Path | None:
    """Nearest parent of this file holding the marker: a source checkout or editable install."""
    for parent in Path(__file__).resolve().parents:
        if (parent / MARKER).is_file():
            return parent
    return None


def _packaged_data_dir() -> Path:
    return Path(str(files("pulseai"))) / "_data"


@cache
def engine_root() -> Path:
    """Return the directory that holds schema/, defaults/, taxonomy/, sources/ and locales/.

    Lookup order: the PULSE_ENGINE_DATA override, a source checkout (so editable installs always
    use live files), then data bundled in the installed wheel.
    """
    override = os.environ.get(ENGINE_DATA_ENV)
    if override:
        root = Path(override).expanduser().resolve()
        if not (root / MARKER).is_file():
            msg = f"{ENGINE_DATA_ENV}={override} does not contain {MARKER}"
            raise EngineDataError(msg)
        return root
    checkout = _checkout_root()
    if checkout is not None:
        return checkout
    packaged = _packaged_data_dir()
    if (packaged / MARKER).is_file():
        return packaged
    msg = f"engine data not found; reinstall pulseai or set {ENGINE_DATA_ENV}"
    raise EngineDataError(msg)


def data_path(*parts: str) -> Path:
    """Path inside the engine data directory."""
    return engine_root().joinpath(*parts)
