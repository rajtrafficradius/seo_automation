from tr_seo_contracts.module0 import (
    BusinessType,
    Module0Request,
    RobotsTxtStatus,
    SitemapStatus,
)
from tr_seo_module0.openai_site_inference import OpenAISiteInferenceResult
from tr_seo_module0.site_inspector import SiteInspector
from tr_seo_module0.website_crawler import CrawledPage, WebsiteCrawlResult


class FakeRobotsInspector:
    def inspect(self, website_url: str) -> RobotsTxtStatus:
        return RobotsTxtStatus(
            url=f"{website_url.rstrip('/')}/robots.txt",
            fetched=True,
            status_code=200,
            allows_ai_crawlers=True,
        )


class FakeSitemapService:
    def discover(self, root_url: str, sitemap_directives: list[str]):
        return (
            SitemapStatus(
                discovered=True,
                sitemap_urls=[f"{root_url.rstrip('/')}/sitemap.xml"],
                fetched_count=1,
                url_count=3,
                sample_urls=[
                    f"{root_url.rstrip('/')}/collections/healthcare-furniture",
                    f"{root_url.rstrip('/')}/collections/commercial-furniture",
                    f"{root_url.rstrip('/')}/about",
                ],
            ),
            [
                f"{root_url.rstrip('/')}/collections/healthcare-furniture",
                f"{root_url.rstrip('/')}/collections/commercial-furniture",
                f"{root_url.rstrip('/')}/about",
            ],
        )


class FakeBlockedCrawler:
    def crawl(self, root_url: str, sitemap_urls: list[str], excluded_pages=None) -> WebsiteCrawlResult:
        return WebsiteCrawlResult(
            homepage_status_code=403,
            response_time_ms=150,
            blocked_reason="anti_bot_interstitial",
            notes=["Homepage content ignored because the site returned a blocked/interstitial page: anti_bot_interstitial."],
            discovered_urls=sitemap_urls,
        )


class FakeBlockedHomepageButPublicPagesCrawler:
    def crawl(self, root_url: str, sitemap_urls: list[str], excluded_pages=None) -> WebsiteCrawlResult:
        return WebsiteCrawlResult(
            homepage_status_code=403,
            final_status_code=200,
            response_time_ms=160,
            blocked_reason="anti_bot_interstitial",
            homepage_text_excerpt=(
                "Healthcare furniture collections for hospitals, clinics, aged care, waiting rooms, "
                "and commercial environments."
            ),
            schema_types=["Organization", "Product"],
            navigation_labels=["Healthcare", "Commercial", "About", "Resources"],
            observed_headings=["Healthcare Furniture", "Commercial Furniture Solutions"],
            framework_hints=["nextjs"],
            crawled_pages=[
                CrawledPage(
                    url=f"{root_url.rstrip('/')}/collections/healthcare-furniture",
                    page_type="category_product",
                    status_code=200,
                    title="Healthcare Furniture",
                    text_excerpt="Healthcare furniture collections for hospitals and clinics.",
                    framework_hints=["nextjs"],
                ),
                CrawledPage(
                    url=f"{root_url.rstrip('/')}/collections/commercial-furniture",
                    page_type="category_product",
                    status_code=200,
                    title="Commercial Furniture",
                    text_excerpt="Commercial furniture for education, workplace and public spaces.",
                    framework_hints=["nextjs"],
                ),
            ],
            discovered_urls=sitemap_urls,
            notes=["Homepage blocked, but public product/category pages were crawled safely."],
        )


class FakeHealthyCrawler:
    def crawl(self, root_url: str, sitemap_urls: list[str], excluded_pages=None) -> WebsiteCrawlResult:
        return WebsiteCrawlResult(
            homepage_status_code=200,
            final_status_code=200,
            response_time_ms=210,
            homepage_title="Healthcare Furniture and Commercial Furniture | ECF",
            meta_description="Healthcare furniture, aged care furniture, waiting room seating and commercial furniture solutions.",
            homepage_text_excerpt=(
                "ECF supplies healthcare furniture, aged care furniture, waiting room seating, "
                "tables, chairs and commercial furniture across Australia."
            ),
            schema_types=["Organization", "Product"],
            navigation_labels=["Healthcare Furniture", "Commercial Furniture", "About", "Resources"],
            observed_headings=["Healthcare Furniture", "Commercial Furniture", "Waiting Room Seating"],
            framework_hints=["nextjs"],
            generator_hints=["Next.js"],
            crawled_pages=[
                CrawledPage(
                    url=f"{root_url.rstrip('/')}/collections/healthcare-furniture",
                    page_type="category_product",
                    status_code=200,
                    title="Healthcare Furniture",
                    text_excerpt="Healthcare furniture collections for hospitals, clinics and aged care environments.",
                    framework_hints=["nextjs"],
                ),
                CrawledPage(
                    url=f"{root_url.rstrip('/')}/collections/commercial-furniture",
                    page_type="category_product",
                    status_code=200,
                    title="Commercial Furniture",
                    text_excerpt="Commercial furniture for offices, education, and public spaces.",
                    framework_hints=["nextjs"],
                ),
            ],
            discovered_urls=sitemap_urls,
            notes=["Crawled 2 HTML pages safely for Module 0 extraction."],
        )


class FakeOpenAISiteInferenceService:
    def is_configured(self) -> bool:
        return True

    def infer(self, request, site_classification, website_profile):
        return OpenAISiteInferenceResult(
            business_type=BusinessType.ECOMMERCE,
            industry_category="healthcare_and_commercial_furniture",
            geographic_target="national_or_catalog_scope",
            language="en-au",
            active_components=["category_product_model", "content_hub"],
            notes=["AI refinement reinforced the ecommerce/catalog interpretation from public evidence."],
            confidence_score=0.84,
        )


def _request() -> Module0Request:
    return Module0Request(
        website_url="https://www.ecf.com.au",
        target_country="au",
        brand_name="Eastern Commercial Furniture & Healthcare Furniture",
        business_type=BusinessType.UNKNOWN,
        services_or_products=["Healthcare furniture", "Commercial furniture"],
        target_locations=["Melbourne"],
        business_goals=["Increase enquiries"],
        priority_services=["Healthcare furniture"],
    )


def test_site_inspector_avoids_blocked_interstitial_content() -> None:
    inspector = SiteInspector(
        robots_inspector=FakeRobotsInspector(),
        sitemap_service=FakeSitemapService(),
        website_crawler=FakeBlockedCrawler(),
    )

    classification, profile = inspector.inspect(_request())

    assert profile.homepage_status_code == 403
    assert profile.homepage_title
    assert profile.canonical_url == "https://www.ecf.com.au/"
    assert profile.homepage_text_excerpt
    assert classification.notes
    assert any("blocked/interstitial" in note for note in classification.notes)
    assert classification.business_type in {BusinessType.ECOMMERCE, BusinessType.HYBRID, BusinessType.UNKNOWN}
    assert classification.cms in {"shopify", "catalog_platform_unverified", "partially_restricted_platform_unverified"}
    assert classification.site_scale_tier == "<500"
    assert classification.page_builder in {"catalog_template_system_unverified", "not_detected_from_safe_crawl"}
    assert classification.theme_or_template in {"catalog_theme_unverified", "standard_theme_unverified"}


def test_site_inspector_uses_crawled_content_for_product_business_inference() -> None:
    inspector = SiteInspector(
        robots_inspector=FakeRobotsInspector(),
        sitemap_service=FakeSitemapService(),
        website_crawler=FakeHealthyCrawler(),
    )

    classification, profile = inspector.inspect(_request())

    assert classification.business_type in {BusinessType.ECOMMERCE, BusinessType.HYBRID}
    assert classification.site_scale_tier == "<500"
    assert classification.cms in {"shopify", "nextjs_custom_stack", "catalog_platform_unverified", "custom_platform_unverified"}
    assert classification.page_builder in {"nextjs_frontend", "catalog_template_system_unverified"}
    assert classification.theme_or_template == "catalog_theme_unverified"
    assert profile.homepage_title == "Healthcare Furniture and Commercial Furniture | ECF"
    assert "Healthcare Furniture" in profile.sample_page_titles
    assert profile.url_inventory.total_urls >= 2
    assert "category_product_model" in classification.active_components


def test_site_inspector_uses_public_pages_when_homepage_is_blocked() -> None:
    inspector = SiteInspector(
        robots_inspector=FakeRobotsInspector(),
        sitemap_service=FakeSitemapService(),
        website_crawler=FakeBlockedHomepageButPublicPagesCrawler(),
    )

    classification, profile = inspector.inspect(_request())

    assert classification.business_type in {BusinessType.ECOMMERCE, BusinessType.HYBRID}
    assert profile.homepage_status_code == 403
    assert profile.final_status_code == 200
    assert profile.homepage_text_excerpt is not None
    assert profile.homepage_title == "Healthcare Furniture"
    assert "Healthcare Furniture" in profile.sample_page_titles
    assert classification.notes
    assert classification.cms in {"shopify", "nextjs_custom_stack", "catalog_platform_unverified", "partially_restricted_platform_unverified"}


def test_site_inspector_applies_ai_inference_when_signals_are_partial() -> None:
    inspector = SiteInspector(
        robots_inspector=FakeRobotsInspector(),
        sitemap_service=FakeSitemapService(),
        website_crawler=FakeBlockedHomepageButPublicPagesCrawler(),
        openai_site_inference_service=FakeOpenAISiteInferenceService(),
    )

    classification, profile = inspector.inspect(_request())

    assert classification.business_type == BusinessType.ECOMMERCE
    assert classification.industry_category == "healthcare_and_commercial_furniture"
    assert classification.language in {"en", "en-au"}
    assert "content_hub" in classification.active_components
    assert any("AI refinement" in note for note in classification.notes)
    assert profile.service_terminology
