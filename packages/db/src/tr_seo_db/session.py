from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tr_seo_db.base import Base


def build_engine(database_url: str):
    return create_engine(database_url, future=True, pool_pre_ping=True)


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = build_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ensure_schema(database_url: str) -> None:
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
