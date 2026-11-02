"""Validated configuration; secrets are never part of tool responses."""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    description: str
    url: SecretStr
    schemas: list[str] = Field(default_factory=lambda: ["public"], min_length=1)

    @field_validator("schemas")
    @classmethod
    def safe_schemas(cls, values: list[str]) -> list[str]:
        if any(
            not s.isidentifier() or s.startswith("pg_") or s == "information_schema" for s in values
        ):
            raise ValueError("Only explicit application schemas are allowed")
        return values


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    databases_json: SecretStr = SecretStr("[]")
    database_config_file: Path | None = None
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    statement_timeout_ms: int = Field(default=3000, ge=10, le=30000)
    max_rows: int = Field(default=100, ge=1, le=1000)
    max_cell_chars: int = Field(default=4000, ge=100, le=10000)
    max_agent_turns: int = Field(default=12, ge=1, le=30)

    def databases(self) -> list[DatabaseConfig]:
        raw = (
            self.database_config_file.read_text(encoding="utf-8")
            if self.database_config_file
            else self.databases_json.get_secret_value()
        )
        databases = [DatabaseConfig.model_validate(item) for item in json.loads(raw)]
        if len({d.id for d in databases}) != len(databases):
            raise ValueError("Database identifiers must be unique")
        return databases


@lru_cache
def get_settings() -> Settings:
    return Settings()
