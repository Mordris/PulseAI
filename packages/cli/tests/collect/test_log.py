import json
from collections.abc import Iterator

import pytest
import structlog

from pulseai.collect.log import configure_logging


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    yield
    structlog.reset_defaults()


def test_json_logs_go_to_stderr_from_warning_up(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(json=True, verbose=False)
    log = structlog.get_logger("test")

    log.info("hidden")
    log.warning("rate_limit_wait", url="https://example.com/feed", status=429)

    out, err = capsys.readouterr()
    assert out == ""
    record = json.loads(err)
    assert record["event"] == "rate_limit_wait"
    assert record["level"] == "warning"
    assert (record["url"], record["status"]) == ("https://example.com/feed", 429)
    assert record["timestamp"].endswith("Z")


def test_verbose_console_logs_include_debug(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(json=False, verbose=True)

    structlog.get_logger("test").debug("fetch", url="https://example.com/feed")

    out, err = capsys.readouterr()
    assert out == ""
    assert "fetch" in err
    assert "https://example.com/feed" in err
