from tr_seo_contracts.module0 import (
    BusinessType,
    KeywordCluster,
    KeywordIntent,
    KeywordOpportunity,
    KeywordPriority,
)
from tr_seo_module0.url_mapper import UrlMapper


def test_url_mapper_builds_clean_service_roots_and_geo_pages() -> None:
    mapper = UrlMapper()

    items = mapper.build_map(
        business_type=BusinessType.SERVICE,
        brand_name="Melbourne Gutter Replacements",
        target_locations=["Melbourne", "Richmond"],
        clusters=[
            KeywordCluster(
                cluster_id="gutter-replacement",
                label="gutter replacement melbourne",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="gutter replacement melbourne",
                keywords=[
                    "gutter replacement melbourne",
                    "gutter replacement cost melbourne",
                    "roof gutter replacement melbourne",
                ],
                total_search_volume=500,
            ),
            KeywordCluster(
                cluster_id="emergency-repair",
                label="emergency gutter repair",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="emergency gutter repair",
                keywords=["emergency gutter repair", "leaking gutter repair melbourne"],
                total_search_volume=220,
            ),
        ],
        existing_urls=[
            "https://example.com/",
            "https://example.com/services/gutter-replacement",
            "https://example.com/services/emergency-gutter-repair",
        ],
        services_or_products=["Gutter replacement", "Emergency gutter repair"],
    )

    proposed_urls = {item.proposed_url for item in items}
    assert "/services/gutter-replacement" in proposed_urls
    assert "/services/emergency-gutter-repair" in proposed_urls
    assert "/services/gutter-replacement/melbourne" in proposed_urls
    assert all("cost" not in path for path in proposed_urls)
    assert all("how-much" not in path for path in proposed_urls)


def test_url_mapper_reuses_collection_style_paths_for_ecommerce() -> None:
    mapper = UrlMapper()

    items = mapper.build_map(
        business_type=BusinessType.ECOMMERCE,
        brand_name="Eastern Commercial Furniture",
        target_locations=["Melbourne"],
        clusters=[
            KeywordCluster(
                cluster_id="healthcare-furniture",
                label="healthcare furniture",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="healthcare furniture",
                keywords=["healthcare furniture", "healthcare furniture melbourne"],
                total_search_volume=900,
            ),
            KeywordCluster(
                cluster_id="commercial-office-chairs",
                label="commercial office chairs",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="commercial office chairs",
                keywords=["commercial office chairs", "office chairs melbourne"],
                total_search_volume=650,
            ),
        ],
        existing_urls=[
            "https://example.com/",
            "https://example.com/collections/healthcare-furniture",
            "https://example.com/collections/commercial-office-chairs",
        ],
        services_or_products=["Healthcare furniture", "Commercial office chairs"],
    )

    category_items = [item for item in items if item.page_type == "category"]
    proposed_urls = {item.proposed_url for item in category_items}
    assert "/collections/healthcare-furniture" in proposed_urls
    assert "/collections/commercial-office-chairs" in proposed_urls
    assert all(not path.startswith("/services/") for path in proposed_urls)
    assert all(item.priority in {KeywordPriority.P1, KeywordPriority.P2} for item in category_items)


def test_url_mapper_ignores_navigation_and_crawl_artifact_clusters() -> None:
    mapper = UrlMapper()

    items = mapper.build_map(
        business_type=BusinessType.SERVICE,
        brand_name="Melbourne Gutter Replacements",
        target_locations=["Melbourne"],
        clusters=[
            KeywordCluster(
                cluster_id="noise-cluster",
                label="observed urls about gallery",
                intent=KeywordIntent.INFORMATIONAL,
                primary_keyword="observed urls about gallery",
                keywords=["observed urls about gallery", "about gallery melbourne"],
                total_search_volume=1200,
            ),
            KeywordCluster(
                cluster_id="real-cluster",
                label="downpipe replacement melbourne",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="downpipe replacement melbourne",
                keywords=["downpipe replacement melbourne", "emergency downpipe replacement"],
                total_search_volume=450,
            ),
        ],
        existing_urls=[
            "https://example.com/",
            "https://example.com/downpipe-replacement",
            "https://example.com/about",
            "https://example.com/gallery",
        ],
        services_or_products=["Downpipe replacement", "Gutter replacement"],
    )

    proposed_urls = {item.proposed_url for item in items}
    assert "/services/observed-urls-about-gallery" not in proposed_urls
    assert all("gallery" not in item.primary_keyword for item in items if item.page_type != "homepage")
    assert any("downpipe replacement" in item.primary_keyword for item in items)


def test_url_mapper_uses_contextual_root_for_question_style_service_queries() -> None:
    mapper = UrlMapper()

    items = mapper.build_map(
        business_type=BusinessType.SERVICE,
        brand_name="Melbourne Gutter Replacements",
        target_locations=["Melbourne"],
        clusters=[
            KeywordCluster(
                cluster_id="fascia-cost",
                label="how much does fascia replacement cost",
                intent=KeywordIntent.INFORMATIONAL,
                primary_keyword="how much does fascia replacement cost",
                keywords=[
                    "how much does fascia replacement cost",
                    "fascia replacement melbourne",
                ],
                total_search_volume=320,
            ),
        ],
        existing_urls=[
            "https://example.com/",
            "https://example.com/services/fascia-replacement",
        ],
        services_or_products=["Fascia replacement", "Gutter replacement"],
    )

    proposed_urls = {item.proposed_url for item in items}
    assert "/services/fascia-replacement" in proposed_urls
    assert all("much-fascia-replacement" not in path for path in proposed_urls)


def test_url_mapper_reuses_root_level_service_pattern_when_site_uses_it() -> None:
    mapper = UrlMapper()

    items = mapper.build_map(
        business_type=BusinessType.SERVICE,
        brand_name="Melbourne Gutter Replacements",
        target_locations=["Melbourne"],
        clusters=[
            KeywordCluster(
                cluster_id="downpipe-replacement",
                label="downpipe replacement",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="downpipe replacement",
                keywords=["downpipe replacement", "downpipe replacement melbourne"],
                total_search_volume=320,
            ),
            KeywordCluster(
                cluster_id="guttering-installation",
                label="guttering installation",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="guttering installation",
                keywords=["guttering installation"],
                total_search_volume=170,
            ),
        ],
        existing_urls=[
            "https://example.com/",
            "https://example.com/downpipe-replacement",
            "https://example.com/fascia-replacement",
        ],
        services_or_products=["Downpipe replacement", "Guttering installation"],
    )

    proposed_urls = {item.proposed_url for item in items if item.page_type in {"service", "subservice"}}
    assert "/downpipe-replacement" in proposed_urls
    assert "/guttering-installation" in proposed_urls
    assert all(not path.startswith("/services/") for path in proposed_urls)


def test_url_mapper_uses_keyword_url_hints_and_nested_subservice_structure() -> None:
    mapper = UrlMapper()

    items = mapper.build_map(
        business_type=BusinessType.SERVICE,
        brand_name="Melbourne Gutter Replacements",
        target_locations=["Melbourne"],
        clusters=[
            KeywordCluster(
                cluster_id="fascia-replacement",
                label="fascia replacement",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="fascia replacement",
                keywords=["fascia replacement", "fascia replacement melbourne"],
                total_search_volume=280,
            ),
            KeywordCluster(
                cluster_id="fascia-guttering-replacement",
                label="fascia guttering replacement",
                intent=KeywordIntent.TRANSACTIONAL,
                primary_keyword="fascia guttering replacement",
                keywords=["fascia guttering replacement", "guttering and fascia replacement"],
                total_search_volume=170,
            ),
        ],
        existing_urls=[
            "https://example.com/",
            "https://example.com/fascia-replacement",
        ],
        keyword_universe=[
            KeywordOpportunity(
                keyword="fascia replacement",
                priority=KeywordPriority.P1,
                mapped_url="https://example.com/fascia-replacement",
            ),
            KeywordOpportunity(
                keyword="fascia guttering replacement",
                priority=KeywordPriority.P2,
                mapped_url="https://example.com/fascia-replacement/fascia-guttering-replacement",
            ),
        ],
        services_or_products=["Fascia replacement", "Fascia guttering replacement"],
    )

    fascia_parent = next(item for item in items if item.primary_keyword == "fascia replacement")
    fascia_child = next(item for item in items if item.primary_keyword == "fascia guttering replacement")
    assert fascia_parent.proposed_url == "/fascia-replacement"
    assert fascia_child.proposed_url == "/fascia-replacement/fascia-guttering-replacement"
    assert fascia_child.hierarchy_level == "L3"
    assert fascia_child.page_type == "subservice"
