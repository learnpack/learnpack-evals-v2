import pytest

from app.config import get_settings


@pytest.fixture(scope="session")
def requires_db() -> None:
    """Skip tests that need a real database when DATABASE_URL is not configured."""
    if not get_settings().database_url:
        pytest.skip("DATABASE_URL not set")
