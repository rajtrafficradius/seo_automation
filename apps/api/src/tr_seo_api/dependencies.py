from __future__ import annotations

from pathlib import Path

from tr_seo_api.config import Settings, get_settings


def get_app_settings() -> Settings:
    return get_settings()


def ensure_upload_dir(settings: Settings) -> Path:
    upload_dir = Path(settings.module0_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir
