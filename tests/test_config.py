import json

import pytest
from pydantic import ValidationError

from app.config import DatabaseConfig, Settings


def test_secret_redaction():
    config = DatabaseConfig(id="demo", description="demo", url="postgresql://user:SECRET@host/db")
    assert "SECRET" not in repr(config)


def test_duplicate_ids():
    entry = {"id": "demo", "description": "demo", "url": "postgresql://localhost/db"}
    with pytest.raises(ValueError):
        Settings(databases_json=json.dumps([entry, entry])).databases()


@pytest.mark.parametrize("schema", ["pg_catalog", "information_schema", "a;drop", "pg_temp"])
def test_schema_config(schema):
    with pytest.raises(ValidationError):
        DatabaseConfig(id="demo", description="demo", url="x", schemas=[schema])
