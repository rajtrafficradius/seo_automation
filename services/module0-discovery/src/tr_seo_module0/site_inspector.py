from __future__ import annotations

import time
from urllib.parse import urlparse
import re

import httpx
from bs4 import BeautifulSoup

from tr_seo_contracts.module0 import (
    BusinessType,
    Module0Request,
    SiteClassification,
    WebsiteProfile,
)
from tr_seo_module0.openai_site_inference import OpenAISiteInferenceError, OpenAISiteInferenceService
from tr_seo_module0.platform_detector import PlatformDetector
from tr_seo_module0.robots_inspector import RobotsInspector
from tr_seo_module0.sitemap_service import SitemapService
from tr_seo_module0.url_inventory import UrlInventoryService
from tr_seo_module0.website_crawler import WebsiteCrawler


class SiteInspector:
    IMPORTANT_HEADERS = [
        "server",
        "content-type",
        "cache-control",
        "x-powered-by",
        "x-frame-options",
        "strict-transport-security",
    ]

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        robots_inspector: RobotsInspector | None = None,
        sitemap_service: SitemapService | None = None,
        platform_detector: PlatformDetector | None = None,
        url_inventory_service: UrlInventoryService | None = None,
        website_crawler: WebsiteCrawler | None = None,
        openai_site_inference_service: OpenAISiteInferenceService | None = None,
    ) -> None:
        self.http_client = http_client
        self.robots_inspector = robots_inspector or RobotsInspector(http_client=http_client)
        self.sitemap_service = sitemap_service or SitemapService(http_client=http_client)
        self.platform_detector = platform_detector or PlatformDetector()
        self.url_inventory_service = url_inventory_service or UrlInventoryService()
        self.website_crawler = website_crawler or WebsiteCrawler()
        self.openai_site_inference_service = openai_site_inference_service or OpenAISiteInferenceService()

    def inspect(self, request: Module0Request) -> tuple[SiteClassification, WebsiteProfile]:
        parsed = urlparse(str(request.website_url))
        root_url = f"{parsed.scheme or 'https'}://{parsed.netloc}"
        domain = (request.domain or parsed.netloc or "").lower()

        robots_status = self.robots_inspector.inspect(root_url)
        sitemap_status, sitemap_urls = self.sitemap_service.discover(
            root_url=root_url,
            sitemap_directives=robots_status.sitemap_directives,
        )
        crawl_result = self.website_crawler.crawl(
            root_url=root_url,
            sitemap_urls=sitemap_urls,
            excluded_pages=request.excluded_services_or_pages,
        )
        discovered_urls = crawl_result.discovered_urls or sitemap_urls
        url_inventory = self.url_inventory_service.summarize(
            discovered_urls,
            excluded_pages=request.excluded_services_or_pages,
        )
        html = crawl_result.homepage_html or ""
        headers: dict[str, str] = {
            key.lower(): value
            for key, value in (crawl_result.homepage_headers or {}).items()
            if key.lower() in self.IMPORTANT_HEADERS
        }
        homepage_status_code = crawl_result.homepage_status_code
        final_status_code = crawl_result.final_status_code
        response_time_ms = crawl_result.response_time_ms
        title = crawl_result.homepage_title
        meta_description = crawl_result.meta_description
        canonical_url = crawl_result.canonical_url
        homepage_text_excerpt = crawl_result.homepage_text_excerpt
        language = crawl_result.language
        h1_count = crawl_result.h1_count
        word_count = crawl_result.word_count
        mobile_friendly = crawl_result.mobile_friendly
        broken_internal_links = crawl_result.broken_internal_links
        indexable = crawl_result.indexable
        redirect_count = crawl_result.redirect_count
        schema_types = crawl_result.schema_types
        social_profile_links = crawl_result.social_profile_links
        observed_headings = crawl_result.observed_headings
        navigation_labels = crawl_result.navigation_labels
        representative_page = self._representative_page(crawl_result.crawled_pages)
        sample_page_titles = self._sample_titles_from_crawl(crawl_result)
        title, meta_description, canonical_url, homepage_text_excerpt = self._resolve_profile_fallbacks(
            request=request,
            root_url=root_url,
            title=title,
            meta_description=meta_description,
            canonical_url=canonical_url,
            homepage_text_excerpt=homepage_text_excerpt,
            sample_page_titles=sample_page_titles,
            url_inventory=url_inventory.sample_urls,
            crawl_blocked=bool(crawl_result.blocked_reason),
        )
        if representative_page is not None:
            final_status_code = final_status_code or representative_page.status_code
            if representative_page.meta_description and meta_description.startswith(request.brand_name):
                meta_description = representative_page.meta_description
            if representative_page.canonical_url and canonical_url == root_url.rstrip("/") + "/":
                canonical_url = representative_page.canonical_url
            if not homepage_text_excerpt and representative_page.text_excerpt:
                homepage_text_excerpt = representative_page.text_excerpt

        platform = self.platform_detector.detect(
            html=html,
            headers=headers,
            sample_urls=discovered_urls,
            sample_titles=sample_page_titles,
            schema_types=schema_types,
            navigation_labels=navigation_labels,
            framework_hints=crawl_result.framework_hints,
            generator_hints=crawl_result.generator_hints,
        )
        cms_value = self._resolve_cms_value(platform, crawl_result.blocked_reason, discovered_urls, sample_page_titles)
        page_builder = self._resolve_optional_label(
            platform.get("page_builder"),
            crawl_result.blocked_reason,
            fallback=self._infer_page_builder(discovered_urls, sample_page_titles),
        )
        theme_or_template = self._resolve_optional_label(
            platform.get("theme_or_template"),
            crawl_result.blocked_reason,
            fallback=self._infer_theme_label(cms_value, business_context=" ".join(sample_page_titles)),
        )
        business_type = request.business_type
        notes: list[str] = []
        confidence = 0.5
        if business_type == BusinessType.UNKNOWN:
            business_type = self._infer_business_type(
                request,
                url_inventory.sample_urls,
                sample_page_titles,
                homepage_text_excerpt,
            )
            notes.append("Business type inferred from frontend inputs, crawled pages, and discovered URLs.")
        else:
            confidence = 0.9

        if crawl_result.blocked_reason:
            notes.append(
                f"Website crawl encountered a block/interstitial condition: {crawl_result.blocked_reason}. "
                "Module 0 continued with sitemap, homepage status, and user-input fallbacks."
            )
            if crawl_result.crawled_pages:
                confidence = max(confidence, 0.62)
            else:
                confidence = min(confidence, 0.45)
        elif crawl_result.crawled_pages:
            confidence = max(confidence, 0.78 if business_type != BusinessType.UNKNOWN else 0.68)

        site_scale_tier = self._site_scale_tier(sitemap_status.url_count)
        if site_scale_tier == "unknown":
            site_scale_tier = self._site_scale_tier(url_inventory.total_urls)
        if site_scale_tier == "unknown":
            site_scale_tier = self._provisional_site_scale(
                discovered_urls=discovered_urls,
                crawl_blocked=bool(crawl_result.blocked_reason),
                crawled_page_count=len(crawl_result.crawled_pages),
            )
        if site_scale_tier == "unknown":
            notes.append("Site scale could not be confirmed from sitemap discovery or safe crawl results.")
        elif site_scale_tier.startswith("provisional_"):
            notes.append("Site scale is provisional because no full sitemap volume could be verified.")
        notes.extend(crawl_result.notes[:6])
        industry_category = self._infer_industry_category(
            request=request,
            sample_titles=sample_page_titles,
            content_summary=homepage_text_excerpt,
            sample_urls=discovered_urls,
        )
        geographic_target = self._infer_geographic_target(
            request=request,
            sample_urls=discovered_urls,
            business_type=business_type,
        )
        resolved_language = self._resolve_language(language, request.target_country)
        active_components = self._resolve_active_components(
            platform=platform,
            sample_page_titles=sample_page_titles,
            discovered_urls=discovered_urls,
            schema_types=schema_types,
            business_type_hint=business_type,
            navigation_labels=navigation_labels,
            observed_headings=observed_headings,
        )
        service_terminology = self._derive_service_terminology(
            request=request,
            sample_titles=sample_page_titles,
            observed_headings=observed_headings,
            discovered_urls=discovered_urls,
            homepage_text_excerpt=homepage_text_excerpt,
        )

        site_classification = SiteClassification(
            business_type=business_type,
            detected_domain=domain,
            industry_category=industry_category,
            geographic_target=geographic_target,
            language=resolved_language,
            cms=cms_value,
            cms_version=platform["cms_version"] if isinstance(platform["cms_version"], str) else None,
            site_scale_tier=site_scale_tier,
            page_builder=page_builder,
            sitemap_url=sitemap_status.sitemap_urls[0] if sitemap_status.sitemap_urls else None,
            active_components=active_components,
            theme_or_template=theme_or_template,
            confidence_score=confidence,
            notes=notes,
        )
        profile = WebsiteProfile(
            homepage_status_code=homepage_status_code,
            final_status_code=final_status_code,
            response_time_ms=response_time_ms,
            redirect_count=redirect_count,
            homepage_title=title,
            meta_description=meta_description,
            homepage_text_excerpt=homepage_text_excerpt,
            canonical_url=canonical_url,
            word_count=word_count,
            h1_count=h1_count,
            primary_schema_type=schema_types[0] if schema_types else None,
            mobile_friendly=mobile_friendly,
            broken_internal_links=broken_internal_links,
            indexable=indexable,
            important_headers=headers,
            detected_schema_types=schema_types,
            social_profile_links=social_profile_links,
            sample_page_titles=sample_page_titles,
            observed_headings=observed_headings[:24],
            navigation_labels=navigation_labels[:24],
            service_terminology=service_terminology,
            robots_txt=robots_status,
            sitemap=sitemap_status,
            url_inventory=url_inventory,
        )
        site_classification = self._apply_ai_inference_if_helpful(
            request=request,
            site_classification=site_classification,
            website_profile=profile,
        )
        return site_classification, profile

    def _extract_page_signals(
        self,
        html: str,
    ) -> tuple[str | None, str | None, str | None, str | None, list[str], list[str]]:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else None
        description_tag = soup.find("meta", attrs={"name": "description"})
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        homepage_text_excerpt = self._extract_text_excerpt(soup)

        schema_types: list[str] = []
        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            text = tag.get_text(" ", strip=True)
            for schema in ["Organization", "LocalBusiness", "Article", "FAQPage", "HowTo", "Product", "Service"]:
                if schema.lower() in text.lower() and schema not in schema_types:
                    schema_types.append(schema)

        social_links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if any(domain in href for domain in ["linkedin.com", "facebook.com", "instagram.com", "youtube.com"]):
                social_links.append(href)

        return (
            title,
            description_tag.get("content", "").strip() or None if description_tag else None,
            canonical_tag.get("href", "").strip() or None if canonical_tag else None,
            homepage_text_excerpt,
            schema_types,
            sorted({item for item in social_links if item})[:10],
        )

    def _extract_text_excerpt(self, soup: BeautifulSoup) -> str | None:
        parts: list[str] = []
        for selector in ["h1", "h2", "p", "li"]:
            for element in soup.find_all(selector)[:12]:
                text = element.get_text(" ", strip=True)
                if text and text not in parts:
                    parts.append(text)
                if len(" ".join(parts)) >= 420:
                    joined = " ".join(parts)
                    return joined[:420].strip()
        if not parts:
            return None
        return " ".join(parts)[:420].strip()

    def _sample_titles_from_crawl(self, crawl_result) -> list[str]:
        titles: list[str] = []
        seen: set[str] = set()
        if crawl_result.homepage_title:
            normalized = crawl_result.homepage_title.strip()
            if normalized:
                titles.append(normalized)
                seen.add(normalized.lower())
        for page in crawl_result.crawled_pages[:10]:
            normalized = (page.title or "").strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                titles.append(normalized)
        return titles[:8]

    def _representative_page(self, pages):
        if not pages:
            return None
        ranked = sorted(
            pages,
            key=lambda page: (
                {"service": 0, "category_product": 1, "location": 2, "homepage": 3, "about_contact": 4, "blog": 5, "general": 6}.get(
                    page.page_type,
                    7,
                ),
                -(len(page.text_excerpt or "") + len(page.title or "")),
            ),
        )
        return ranked[0]

    def _resolve_profile_fallbacks(
        self,
        request: Module0Request,
        root_url: str,
        title: str | None,
        meta_description: str | None,
        canonical_url: str | None,
        homepage_text_excerpt: str | None,
        sample_page_titles: list[str],
        url_inventory: list[str],
        crawl_blocked: bool,
    ) -> tuple[str, str, str, str]:
        resolved_title = (title or "").strip()
        if not resolved_title:
            if sample_page_titles:
                resolved_title = sample_page_titles[0]
            else:
                service_hint = request.priority_services[0] if request.priority_services else (
                    request.services_or_products[0] if request.services_or_products else "SEO Discovery"
                )
                resolved_title = f"{request.brand_name} | {service_hint}".strip()

        resolved_canonical = (canonical_url or "").strip() or root_url.rstrip("/") + "/"

        resolved_excerpt = (homepage_text_excerpt or "").strip()
        if not resolved_excerpt:
            summary_parts = []
            if request.services_or_products:
                summary_parts.append("Services/products: " + ", ".join(request.services_or_products[:4]))
            if request.target_locations:
                summary_parts.append("Target locations: " + ", ".join(request.target_locations[:4]))
            if request.business_goals:
                summary_parts.append("Business goals: " + ", ".join(request.business_goals[:3]))
            if sample_page_titles:
                summary_parts.append("Observed pages: " + ", ".join(sample_page_titles[:3]))
            elif url_inventory:
                path_signals = self._path_signal_phrases(url_inventory)
                if path_signals:
                    summary_parts.append("Key site sections: " + ", ".join(path_signals[:4]))
            resolved_excerpt = " ".join(summary_parts).strip() or (
                f"{request.brand_name} website profile inferred from available onboarding and crawl-safe signals."
            )

        resolved_meta = (meta_description or "").strip()
        if not resolved_meta:
            location_text = f" across {', '.join(request.target_locations[:3])}" if request.target_locations else ""
            service_text = ", ".join(request.services_or_products[:3]) if request.services_or_products else "SEO-focused services"
            resolved_meta = (
                f"{request.brand_name} offers {service_text}{location_text}. "
                f"Module 0 summary generated from crawl-safe signals{' with partial website access' if crawl_blocked else ''}."
            )
        return (
            resolved_title[:140],
            resolved_meta[:320],
            resolved_canonical,
            resolved_excerpt[:900],
        )

    def _infer_business_type(
        self,
        request: Module0Request,
        sample_urls: list[str],
        sample_titles: list[str],
        content_summary: str | None,
    ) -> BusinessType:
        values = " ".join(
            request.services_or_products
            + request.priority_services
            + request.business_goals
            + sample_urls
            + sample_titles
            + ([content_summary] if content_summary else [])
        ).lower()
        ecommerce_tokens = {
            "shop",
            "product",
            "products",
            "catalog",
            "buy",
            "collection",
            "collections",
            "furniture",
            "chair",
            "chairs",
            "table",
            "tables",
            "bed",
            "beds",
            "desk",
            "seating",
            "storage",
            "sofa",
            "sofas",
        }
        service_tokens = {
            "service",
            "services",
            "repair",
            "repairs",
            "replacement",
            "installation",
            "install",
            "maintenance",
            "fitout",
            "consulting",
        }
        local_tokens = {"location", "locations", "suburb", "suburbs", "near me", "local"}
        ecommerce_hits = sum(1 for token in ecommerce_tokens if token in values)
        service_hits = sum(1 for token in service_tokens if token in values)
        local_hits = sum(1 for token in local_tokens if token in values)

        if any(token in values for token in {"software", "platform", "saas"}):
            return BusinessType.SAAS
        if ecommerce_hits >= 2 and service_hits >= 2:
            return BusinessType.HYBRID
        if ecommerce_hits >= 2:
            return BusinessType.ECOMMERCE
        if local_hits >= 2 and service_hits >= 1:
            return BusinessType.LOCAL
        if service_hits >= 1:
            return BusinessType.SERVICE
        return BusinessType.UNKNOWN

    def _site_scale_tier(self, url_count: int) -> str:
        if url_count <= 0:
            return "unknown"
        if url_count < 500:
            return "<500"
        if url_count <= 5000:
            return "500-5000"
        return ">5000"

    def _provisional_site_scale(
        self,
        discovered_urls: list[str],
        crawl_blocked: bool,
        crawled_page_count: int,
    ) -> str:
        discovered_count = len({url for url in discovered_urls if url})
        if discovered_count >= 40:
            return "provisional_<500"
        if discovered_count >= 8:
            return "provisional_<500"
        if crawled_page_count >= 2 and not crawl_blocked:
            return "provisional_<500"
        if discovered_count > 0:
            return "provisional_<500"
        return "unknown"

    def _resolve_cms_value(
        self,
        platform: dict[str, str | list[str] | None],
        blocked_reason: str | None,
        discovered_urls: list[str],
        sample_page_titles: list[str],
    ) -> str:
        cms = str(platform.get("cms") or "").strip().lower()
        if cms and cms != "unknown":
            return cms
        framework = str(platform.get("framework") or "").strip().lower()
        if framework:
            return f"{framework}_stack_unverified"
        url_blob = " ".join(discovered_urls).lower()
        if any(token in url_blob for token in ["collections/", "/products/", "product/"]):
            return "catalog_platform_unverified"
        title_blob = " ".join(sample_page_titles).lower()
        if any(token in title_blob for token in ["shop", "product", "collection", "catalog"]):
            return "catalog_platform_unverified"
        if any(token in url_blob for token in ["wp-content", "wp-json", "/wp/"]):
            return "wordpress_unverified"
        if any(token in url_blob for token in ["shopify", "/collections/", "/products/"]):
            return "shopify_like_unverified"
        if any(token in url_blob for token in ["wix", "wixsite", "wixstatic"]):
            return "wix_unverified"
        if any(token in title_blob for token in ["webflow", "squarespace"]):
            return "frontend_cms_unverified"
        if blocked_reason:
            return "partially_restricted_platform_unverified"
        return "custom_platform_unverified"

    def _resolve_optional_label(self, value, blocked_reason: str | None, fallback: str) -> str | None:
        if isinstance(value, str) and value.strip():
            return value
        return fallback

    def _infer_page_builder(self, discovered_urls: list[str], sample_page_titles: list[str]) -> str:
        title_blob = " ".join(sample_page_titles).lower()
        url_blob = " ".join(discovered_urls).lower()
        if "landing page" in title_blob:
            return "landing_page_builder_unverified"
        if any(token in url_blob for token in ["shop", "collections", "products"]):
            return "catalog_template_system_unverified"
        return "not_detected_from_safe_crawl"

    def _infer_theme_label(self, cms_value: str, business_context: str) -> str:
        if cms_value.startswith("catalog_") or "furniture" in business_context.lower():
            return "catalog_theme_unverified"
        if "service" in business_context.lower() or "repair" in business_context.lower():
            return "service_theme_unverified"
        return "standard_theme_unverified"

    def _resolve_active_components(
        self,
        platform: dict[str, str | list[str] | None],
        sample_page_titles: list[str],
        discovered_urls: list[str],
        schema_types: list[str],
        business_type_hint: BusinessType,
        navigation_labels: list[str],
        observed_headings: list[str],
    ) -> list[str]:
        components = set()
        if isinstance(platform.get("active_components"), list):
            components.update(item for item in platform["active_components"] if item)
        if isinstance(platform.get("fingerprints"), list):
            components.update(item for item in platform["fingerprints"] if item)
        components.update(schema_types[:4])
        url_blob = " ".join(discovered_urls).lower()
        title_blob = " ".join(sample_page_titles).lower()
        nav_blob = " ".join(navigation_labels).lower()
        heading_blob = " ".join(observed_headings).lower()
        if any(token in url_blob for token in ["collections/", "/products/"]):
            components.add("catalog_navigation")
        if any(token in title_blob for token in ["about", "contact", "showroom"]):
            components.add("trust_pages")
        if any(token in nav_blob for token in ["blog", "resources", "guides", "articles"]):
            components.add("content_hub")
        if any(token in heading_blob for token in ["faq", "frequently asked", "common questions"]):
            components.add("faq_content")
        if business_type_hint in {BusinessType.LOCAL, BusinessType.SERVICE}:
            components.add("service_content_model")
        if business_type_hint in {BusinessType.ECOMMERCE, BusinessType.HYBRID}:
            components.add("category_product_model")
        return sorted(item for item in components if item)[:8]

    def _infer_industry_category(
        self,
        request: Module0Request,
        sample_titles: list[str],
        content_summary: str | None,
        sample_urls: list[str],
    ) -> str:
        values = " ".join(
            request.services_or_products
            + request.priority_services
            + sample_titles
            + sample_urls
            + ([content_summary] if content_summary else [])
        ).lower()
        if any(token in values for token in {"gutter", "roofing", "downpipe", "fascia"}):
            return "roofing_and_guttering"
        if any(token in values for token in {"furniture", "chair", "table", "desk", "seating"}):
            if any(token in values for token in {"healthcare", "hospital", "aged care", "clinic"}):
                return "healthcare_and_commercial_furniture"
            return "commercial_furniture"
        if any(token in values for token in {"plumber", "plumbing", "electrician", "electrical", "tradie"}):
            return "trade_services"
        if any(token in values for token in {"seo", "marketing", "agency", "digital"}):
            return "digital_marketing"
        if any(token in values for token in {"software", "saas", "platform", "app"}):
            return "software_and_saas"
        return "general_business_services"

    def _infer_geographic_target(
        self,
        request: Module0Request,
        sample_urls: list[str],
        business_type: BusinessType,
    ) -> str:
        if request.target_locations:
            if len(request.target_locations) == 1:
                return f"local_market:{request.target_locations[0].lower()}"
            return f"multi_location:{', '.join(location.lower() for location in request.target_locations[:4])}"
        url_blob = " ".join(sample_urls).lower()
        if any(token in url_blob for token in ["melbourne", "sydney", "brisbane", "perth", "adelaide"]):
            return "city_targeted_australia"
        if business_type in {BusinessType.ECOMMERCE, BusinessType.HYBRID}:
            return "national_or_catalog_scope"
        return "unverified_market_scope"

    def _resolve_language(self, language: str | None, target_country: str) -> str:
        if language:
            return language
        country = target_country.lower()
        if country in {"au", "us", "uk", "ca", "nz"}:
            return "en"
        return "unverified"

    def _apply_ai_inference_if_helpful(
        self,
        request: Module0Request,
        site_classification: SiteClassification,
        website_profile: WebsiteProfile,
    ) -> SiteClassification:
        if not self.openai_site_inference_service.is_configured():
            return site_classification
        needs_help = (
            site_classification.business_type == BusinessType.UNKNOWN
            or "unverified" in site_classification.cms
            or site_classification.confidence_score < 0.78
            or site_classification.industry_category == "general_business_services"
        )
        if not needs_help:
            return site_classification
        try:
            inference = self.openai_site_inference_service.infer(
                request=request,
                site_classification=site_classification,
                website_profile=website_profile,
            )
        except OpenAISiteInferenceError as error:
            updated = site_classification.model_copy(deep=True)
            updated.notes.append(str(error))
            return updated

        updated = site_classification.model_copy(deep=True)
        if inference.business_type and updated.business_type == BusinessType.UNKNOWN:
            updated.business_type = inference.business_type
        if inference.industry_category and updated.industry_category == "general_business_services":
            updated.industry_category = inference.industry_category
        if inference.geographic_target and updated.geographic_target in {"unverified_market_scope", "national_or_catalog_scope"}:
            updated.geographic_target = inference.geographic_target
        if inference.language and updated.language == "unverified":
            updated.language = inference.language
        if inference.active_components:
            updated.active_components = sorted({*updated.active_components, *inference.active_components})[:10]
        if inference.notes:
            updated.notes.extend(inference.notes[:4])
        updated.confidence_score = max(updated.confidence_score, min(inference.confidence_score, 0.92))
        return updated

    def _path_signal_phrases(self, urls: list[str]) -> list[str]:
        signals: list[str] = []
        seen: set[str] = set()
        noise = {"about", "contact", "gallery", "blog", "page", "pages", "home", "homepage"}
        for item in urls[:8]:
            parts = [part for part in urlparse(item).path.lower().split("/") if part]
            candidate = " ".join(
                part.replace("-", " ").replace("_", " ")
                for part in parts[-2:]
                if part not in noise
            ).strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            signals.append(candidate)
        return signals

    def _derive_service_terminology(
        self,
        request: Module0Request,
        sample_titles: list[str],
        observed_headings: list[str],
        discovered_urls: list[str],
        homepage_text_excerpt: str | None,
    ) -> list[str]:
        values = [
            *request.services_or_products,
            *request.priority_services,
            *sample_titles,
            *observed_headings,
            *(self._path_signal_phrases(discovered_urls[:24])),
            homepage_text_excerpt or "",
        ]
        phrases: list[str] = []
        seen: set[str] = set()
        for raw in values:
            for part in re.split(r"[|,/:\-–]+", raw):
                cleaned = re.sub(r"[^a-z0-9\s]", " ", part.lower())
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                tokens = [
                    token
                    for token in cleaned.split()
                    if len(token) > 2
                    and token
                    not in {
                        "about",
                        "contact",
                        "gallery",
                        "blog",
                        "page",
                        "pages",
                        "home",
                        "homepage",
                        "professional",
                        "services",
                    }
                ]
                if len(tokens) < 2 or len(tokens) > 5:
                    continue
                phrase = " ".join(tokens[:5])
                if phrase in seen:
                    continue
                seen.add(phrase)
                phrases.append(phrase)
                if len(phrases) >= 18:
                    return phrases
        return phrases

    def _client(self):
        if self.http_client is not None:
            return _SharedClientContext(self.http_client)
        return httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0))


class _SharedClientContext:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False
