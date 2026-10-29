from pathlib import Path
from typing import Any

import pytest

CASSETTE_DIR = Path(__file__).parent / "cassettes"
# Request headers that can carry credentials; vcrpy drops them before a cassette is written.
SECRET_HEADERS = ("authorization", "cookie", "set-cookie")


def _without_set_cookie(response: dict[str, Any]) -> dict[str, Any]:
    """vcrpy's filter_headers covers requests only, so cookies a server sets are dropped here."""
    headers = {
        name: values for name, values in response["headers"].items() if name.lower() != "set-cookie"
    }
    return {**response, "headers": headers}


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio only: aiolimiter, used by the fetcher, is asyncio-specific."""
    return "asyncio"


@pytest.fixture(scope="module")
def vcr_cassette_dir() -> str:
    """One folder for every cassette. Each test names its cassette with `default_cassette`."""
    return str(CASSETTE_DIR)


@pytest.fixture
def vcr_config(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Cassette settings: replay only, bodies stored decoded, credentials never written.

    Decoded bodies keep a cassette readable and replay through the fetcher's identity path,
    without a Content-Encoding header. To record a cassette again, delete it and run its test
    with `--record-mode=once`: that is the one place a test may use the network.
    """
    config: dict[str, Any] = {
        "filter_headers": list(SECRET_HEADERS),
        "before_record_response": _without_set_cookie,
        "decode_compressed_response": True,
    }
    # A record_mode in this config would win over `--record-mode`, so set it only when the
    # option is absent. Then `--record-mode=once` can still record a cassette.
    if request.config.getoption("--record-mode") is None:
        config["record_mode"] = "none"
    return config
