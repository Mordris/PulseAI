import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio only: aiolimiter, used by the fetcher, is asyncio-specific."""
    return "asyncio"
