from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError

from tr_seo_api.config import Settings
from tr_seo_api.dependencies import ensure_upload_dir, get_app_settings
from tr_seo_contracts.module0 import (
    BusinessType,
    Module0Request,
    Module0Response,
    RunMessage,
    RunMessageSeverity,
)
from tr_seo_module0.cdd_parser import CDDParser
from tr_seo_module0.exporter import Module0Exporter
from tr_seo_module0.service import Module0Service
from tr_seo_db import Module0Repository, build_session_factory, ensure_schema

router = APIRouter(prefix="/api/v1/module0", tags=["module0"])


def _split_csv_field(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _ensure_export_dir(settings: Settings) -> Path:
    export_dir = ensure_upload_dir(settings) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


@router.post("/runs", response_model=Module0Response)
async def run_module0(
    website_url: str = Form(...),
    domain: str | None = Form(default=None),
    target_country: str = Form(...),
    brand_name: str = Form(...),
    business_type: BusinessType = Form(default=BusinessType.UNKNOWN),
    services_or_products: str = Form(default=""),
    target_locations: str = Form(default=""),
    business_goals: str = Form(default=""),
    priority_services: str = Form(default=""),
    known_competitors: str = Form(default=""),
    excluded_services_or_pages: str = Form(default=""),
    brand_profiles: str = Form(default=""),
    notes: str | None = Form(default=None),
    cdd_file: UploadFile = File(...),
    semrush_keyword_file: UploadFile | None = File(default=None),
    settings: Settings = Depends(get_app_settings),
) -> Module0Response:
    run_id = str(uuid4())
    parser = CDDParser()
    file_bytes = await cdd_file.read()
    file_meta = parser.make_file_meta(
        filename=cdd_file.filename or "cdd-upload",
        content_type=cdd_file.content_type or "application/octet-stream",
        size_bytes=len(file_bytes),
    )

    if file_meta.extension not in CDDParser.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported CDD upload format: {file_meta.extension}",
        )

    upload_dir = ensure_upload_dir(settings)
    safe_name = f"{run_id}-{Path(file_meta.filename).name}"
    destination = upload_dir / safe_name
    destination.write_bytes(file_bytes)

    keyword_file_meta = None
    keyword_file_bytes = None
    if semrush_keyword_file is not None:
        keyword_file_bytes = await semrush_keyword_file.read()
        keyword_file_meta = parser.make_file_meta(
            filename=semrush_keyword_file.filename or "semrush-keyword-upload",
            content_type=semrush_keyword_file.content_type or "application/octet-stream",
            size_bytes=len(keyword_file_bytes),
        )
        if keyword_file_meta.extension not in {".xlsx", ".xls", ".csv"}:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported SEMrush keyword upload format: {keyword_file_meta.extension}",
            )

    request = Module0Request(
        website_url=website_url,
        domain=domain,
        target_country=target_country.lower(),
        brand_name=brand_name,
        business_type=business_type,
        services_or_products=_split_csv_field(services_or_products),
        target_locations=_split_csv_field(target_locations),
        business_goals=_split_csv_field(business_goals),
        priority_services=_split_csv_field(priority_services),
        known_competitors=_split_csv_field(known_competitors),
        excluded_services_or_pages=_split_csv_field(excluded_services_or_pages),
        brand_profiles=_split_csv_field(brand_profiles),
        notes=notes,
    )

    service = Module0Service()
    response = service.run_with_optional_keyword_upload(
        request=request,
        cdd_meta=file_meta,
        cdd_content=file_bytes,
        keyword_file_meta=keyword_file_meta,
        keyword_file_content=keyword_file_bytes,
    )
    exports = Module0Exporter().export(response=response, output_dir=_ensure_export_dir(settings), run_id=run_id)
    response = response.model_copy(update={"exports": exports})

    if settings.module0_persist_to_db:
        try:
            ensure_schema(settings.database_url)
            session_factory = build_session_factory(settings.database_url)
            with session_factory() as session:
                Module0Repository().save_run(
                    session=session,
                    response=response,
                    cdd_storage_path=str(destination),
                )
        except SQLAlchemyError as error:
            warnings = list(response.warnings_errors)
            warnings.append(
                RunMessage(
                    code="db_persist_failed",
                    severity=RunMessageSeverity.WARNING,
                    message=f"Module 0 output was generated but could not be persisted: {error.__class__.__name__}.",
                    source="module0_route",
                )
            )
            response = response.model_copy(update={"warnings_errors": warnings})

    return response


@router.get("/downloads/{filename}", response_model=None)
def download_module0_export(
    filename: str,
    settings: Settings = Depends(get_app_settings),
) -> FileResponse:
    export_dir = _ensure_export_dir(settings).resolve()
    target = (export_dir / Path(filename).name).resolve()
    if not target.is_file() or export_dir not in target.parents:
        raise HTTPException(status_code=404, detail="Export file not found.")
    return FileResponse(
        target,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=target.name,
    )
