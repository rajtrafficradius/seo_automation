from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TR SEO Automation API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://tr_seo:tr_seo@localhost:5432/tr_seo"
    redis_url: str = "redis://localhost:6379/0"
    semrush_api_key: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    module0_test_keyword_limit: int = 200
    module0_production_keyword_limit: int = 1000
    module0_force_mock_semrush: bool = False
    module0_allowed_uploads: str = ".pdf,.docx,.xlsx,.xls,.csv"
    module0_upload_dir: str = "uploads/module0"
    module0_persist_to_db: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
