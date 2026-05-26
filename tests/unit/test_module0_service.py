from tr_seo_contracts.module0 import (
    BusinessType,
    CDDFileMeta,
    Module0Request,
    RobotsTxtStatus,
    SEMrushSnapshot,
    SiteClassification,
    SitemapStatus,
    UrlInventorySummary,
    WebsiteProfile,
)
from tr_seo_module0.service import Module0Service
from tr_seo_module0.semrush_client import (
    SEMrushCollectionResult,
    SEMrushCompetitorRecord,
    SEMrushKeywordRecord,
)


class FakeSiteInspector:
    def inspect(self, request: Module0Request):
        return (
            SiteClassification(
                business_type=BusinessType.SERVICE,
                detected_domain="example.com",
                cms="wordpress",
                site_scale_tier="<500",
                sitemap_url="https://example.com/sitemap.xml",
                confidence_score=0.9,
            ),
            WebsiteProfile(
                homepage_status_code=200,
                response_time_ms=120,
                homepage_title="Example Brand",
                meta_description="Example description",
                homepage_text_excerpt="Gutter replacement, repairs, and downpipe services across Melbourne.",
                canonical_url="https://example.com/",
                important_headers={"server": "nginx"},
                detected_schema_types=["Organization"],
                social_profile_links=["https://linkedin.com/company/example"],
                sample_page_titles=[
                    "Example Brand | Gutter Replacement Melbourne",
                    "Downpipe Replacement Melbourne | Example Brand",
                ],
                robots_txt=RobotsTxtStatus(
                    url="https://example.com/robots.txt",
                    fetched=True,
                    status_code=200,
                    allows_ai_crawlers=True,
                ),
                sitemap=SitemapStatus(
                    discovered=True,
                    sitemap_urls=["https://example.com/sitemap.xml"],
                    fetched_count=1,
                    url_count=4,
                    sample_urls=[
                        "https://example.com/",
                        "https://example.com/services/gutter-replacement",
                    ],
                ),
                url_inventory=UrlInventorySummary(
                    total_urls=4,
                    sample_urls=[
                        "https://example.com/",
                        "https://example.com/services/gutter-replacement",
                    ],
                ),
            ),
        )


class FakeSemrushClient:
    def collect(
        self,
        request: Module0Request,
        cdd_extraction=None,
        site_classification=None,
        website_profile=None,
        manual_keyword_file_meta=None,
        manual_keyword_content=None,
    ) -> SEMrushCollectionResult:
        return SEMrushCollectionResult(
            snapshot=SEMrushSnapshot(
                configured=True,
                region_database="au",
                status="live",
                data_source="semrush",
                fallback_used=False,
                warning_message=None,
                keyword_limit=200,
                estimated_monthly_traffic=400,
                estimated_monthly_traffic_history=[380, 390, 400],
                organic_keyword_count=3,
                competitors_evaluated=1,
            ),
            keywords=[
                SEMrushKeywordRecord(
                    keyword="gutter replacement melbourne",
                    search_volume=210,
                    keyword_difficulty=24,
                    current_position=7,
                    source="semrush",
                    cpc=4.2,
                    mapped_url="https://example.com/services/gutter-replacement",
                ),
                SEMrushKeywordRecord(
                    keyword="example brand gutter replacement",
                    search_volume=80,
                    keyword_difficulty=18,
                    current_position=5,
                    source="semrush",
                    cpc=2.1,
                    mapped_url="https://example.com/services/brand-gutter-replacement",
                ),
                SEMrushKeywordRecord(
                    keyword="how to replace guttering",
                    search_volume=120,
                    keyword_difficulty=42,
                    current_position=11,
                    source="semrush",
                    cpc=1.4,
                ),
            ],
            competitors=[
                SEMrushCompetitorRecord(
                    domain="competitor-a.com.au",
                    competition_level=0.81,
                    shared_keywords=34,
                    keyword_sample=["gutter repair melbourne", "gutter replacement cost"],
                )
            ],
        )


def _request() -> Module0Request:
    return Module0Request(
        website_url="https://example.com",
        target_country="au",
        brand_name="Example Brand",
        business_type=BusinessType.SERVICE,
        services_or_products=["Gutter Replacement"],
        target_locations=["Melbourne"],
        business_goals=["Increase leads"],
        priority_services=["Gutter Replacement"],
    )


def test_module0_service_returns_rich_backend_structure() -> None:
    service = Module0Service(
        site_inspector=FakeSiteInspector(),
        semrush_client=FakeSemrushClient(),
    )

    result = service.run(
        request=_request(),
        cdd_meta=CDDFileMeta(
            filename="cdd.csv",
            content_type="text/csv",
            size_bytes=20,
            extension=".csv",
        ),
        cdd_content=b"field,value",
    )

    assert result.site_classification.detected_domain == "example.com"
    assert result.website_profile.sitemap.discovered is True
    assert result.competitive_intelligence.top_competitors[0].domain == "competitor-a.com.au"
    assert result.master_keyword_universe[0].cluster_id is not None
    assert result.url_architecture_map[0].proposed_url == "/"
    assert result.tam_dataset.p1_p2_search_volume == 290
    assert result.quick_wins.total_count >= 1
    assert result.minimum_effort_points
    assert result.entity_authority_baseline.score > 0
    assert result.ai_sov_baseline.brand_visibility_summary
    assert result.ai_sov_baseline.query_results
    assert any(
        item.mapped_url == "https://example.com/services/gutter-replacement"
        for item in result.master_keyword_universe
        if item.keyword == "gutter replacement melbourne"
    )
