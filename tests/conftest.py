import pytest

from app.config import Settings
from app.database import Registry


@pytest.fixture(scope="session")
def registry():
    settings = Settings()
    if not settings.databases():
        pytest.skip("Configure DATABASES_JSON with seeded databases for integration tests")
    instance = Registry(settings)
    yield instance
    instance.close()
