from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tr_seo_db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    website_url: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_country: Mapped[str] = mapped_column(String(3), nullable=False)
    brand_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    module0_runs: Mapped[list["Module0Run"]] = relationship(back_populates="project")


class Module0Run(Base):
    __tablename__ = "module0_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    semrush_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    semrush_data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cdd_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    cdd_content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    cdd_storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped["Project"] = relationship(back_populates="module0_runs")
    discovery_data: Mapped["DiscoveryData"] = relationship(back_populates="module0_run", uselist=False)


class DiscoveryData(Base):
    __tablename__ = "discovery_data"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    module0_run_id: Mapped[str] = mapped_column(
        ForeignKey("module0_runs.id"), nullable=False, unique=True, index=True
    )
    tam_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cdd_extraction: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    site_classification: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    website_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    semrush_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    competitive_intelligence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    master_keyword_universe: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    keyword_clusters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    quick_wins: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tam_dataset: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    url_architecture_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    minimum_effort_points: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ai_sov_baseline: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    fan_out_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    entity_authority_baseline: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    exports: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    warnings_errors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    run_timestamps: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    module0_run: Mapped["Module0Run"] = relationship(back_populates="discovery_data")
