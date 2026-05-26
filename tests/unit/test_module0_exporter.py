from pathlib import Path
from uuid import uuid4

from tr_seo_contracts.module0 import (
    BusinessType,
    CDDExtraction,
    CDDFileMeta,
    CompetitiveIntelligence,
    Module0Request,
    Module0Response,
    QuickWinSummary,
    RobotsTxtStatus,
    RunTimestamps,
    SEMrushSnapshot,
    SiteClassification,
    SitemapStatus,
    TamDataset,
    UrlArchitectureItem,
    UrlInventorySummary,
    WebsiteProfile,
)
from tr_seo_module0.exporter import Module0Exporter
from tr_seo_module0.service import Module0Service


def _build_response() -> Module0Response:
    service = Module0Service()
    request = Module0Request(
        website_url="https://example.com",
        target_country="au",
        brand_name="Example Brand",
        business_type=BusinessType.SERVICE,
        services_or_products=["Gutter Replacement"],
        target_locations=["Melbourne"],
        business_goals=["Increase leads"],
        priority_services=["Gutter Replacement"],
    )
    return Module0Response(
        request=request,
        cdd_file=CDDFileMeta(
            filename="cdd.csv",
            content_type="text/csv",
            size_bytes=20,
            extension=".csv",
        ),
        cdd_extraction=CDDExtraction(
            text_preview="preview",
            parser_used="csv",
        ),
        site_classification=SiteClassification(
            business_type=BusinessType.SERVICE,
            detected_domain="example.com",
            cms="wordpress",
            site_scale_tier="<500",
            sitemap_url="https://example.com/sitemap.xml",
        ),
        website_profile=WebsiteProfile(
            homepage_status_code=200,
            response_time_ms=100,
            homepage_title="Example",
            meta_description="Example description",
            canonical_url="https://example.com/",
            important_headers={"server": "nginx"},
            detected_schema_types=["Organization"],
            social_profile_links=["https://linkedin.com/company/example"],
            robots_txt=RobotsTxtStatus(url="https://example.com/robots.txt", fetched=True),
            sitemap=SitemapStatus(discovered=True, sitemap_urls=["https://example.com/sitemap.xml"], url_count=2),
            url_inventory=UrlInventorySummary(total_urls=2, sample_urls=["https://example.com/"]),
        ),
        semrush=SEMrushSnapshot(
            configured=True,
            region_database="au",
            status="live",
            data_source="semrush",
            fallback_used=False,
            warning_message=None,
            keyword_limit=200,
            estimated_monthly_traffic=400,
            organic_keyword_count=3,
            competitors_evaluated=1,
        ),
        competitive_intelligence=CompetitiveIntelligence(),
        master_keyword_universe=[],
        keyword_universe_preview=[],
        keyword_clusters=[],
        quick_wins=QuickWinSummary(total_count=0),
        tam_estimate=210,
        tam_dataset=TamDataset(
            total_monthly_search_volume=210,
            p1_p2_search_volume=210,
            current_capture_estimate=100,
            opportunity_gap=110,
            current_share_ratio=0.47,
            methodology="test",
        ),
        url_architecture_map=[
            UrlArchitectureItem(
                hierarchy_level="L2",
                page_type="service",
                proposed_url="/services/gutter-replacement",
                primary_keyword="gutter replacement melbourne",
            )
        ],
        url_architecture_preview=[
            UrlArchitectureItem(
                hierarchy_level="L2",
                page_type="service",
                proposed_url="/services/gutter-replacement",
                primary_keyword="gutter replacement melbourne",
            )
        ],
        minimum_effort_points=[],
        ai_sov_baseline=service.ai_sov_service.build([], "Example Brand"),
        fan_out_map=service.fanout_mapper.build([], [], []),
        entity_authority_baseline=service.entity_authority_service.build(
            "Example Brand",
            ["https://linkedin.com/company/example"],
            [],
            ["Organization"],
        ),
        run_timestamps=RunTimestamps(),
    )


def test_module0_exporter_creates_xlsx_files(tmp_path: Path) -> None:
    response = _build_response()
    output_dir = tmp_path / f"module0-export-{uuid4().hex}"
    output_dir.mkdir(parents=True, exist_ok=True)

    exports = Module0Exporter().export(response=response, output_dir=output_dir, run_id="run-123")

    assert exports.keyword_universe.filename == "example_brand_master_keyword_universe.xlsx"
    assert exports.full_run_workbook.filename == "example_brand_module0_full_export.xlsx"

    assert exports.cdd_extraction is not None
    assert exports.site_classification is not None
    assert exports.website_profile is not None
    assert exports.semrush_snapshot is not None
    assert exports.competitive_intelligence is not None
    assert exports.keyword_universe is not None
    assert exports.keyword_clusters is not None
    assert exports.quick_wins is not None
    assert exports.tam_dataset is not None
    assert exports.url_architecture_map is not None
    assert exports.minimum_effort_points is not None
    assert exports.ai_sov_baseline is not None
    assert exports.fan_out_map is not None
    assert exports.entity_authority_baseline is not None
    assert exports.warnings_errors is not None
    assert exports.full_run_workbook is not None
    assert (output_dir / exports.cdd_extraction.filename).exists()
    assert (output_dir / exports.site_classification.filename).exists()
    assert (output_dir / exports.website_profile.filename).exists()
    assert (output_dir / exports.semrush_snapshot.filename).exists()
    assert (output_dir / exports.competitive_intelligence.filename).exists()
    assert (output_dir / exports.keyword_universe.filename).exists()
    assert (output_dir / exports.keyword_clusters.filename).exists()
    assert (output_dir / exports.quick_wins.filename).exists()
    assert (output_dir / exports.tam_dataset.filename).exists()
    assert (output_dir / exports.url_architecture_map.filename).exists()
    assert (output_dir / exports.minimum_effort_points.filename).exists()
    assert (output_dir / exports.ai_sov_baseline.filename).exists()
    assert (output_dir / exports.fan_out_map.filename).exists()
    assert (output_dir / exports.entity_authority_baseline.filename).exists()
    assert (output_dir / exports.warnings_errors.filename).exists()
    assert (output_dir / exports.full_run_workbook.filename).exists()
