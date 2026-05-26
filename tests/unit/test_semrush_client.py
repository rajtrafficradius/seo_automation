import json

import httpx

from tr_seo_contracts.module0 import (
    BusinessType,
    CDDFileMeta,
    CDDExtraction,
    Module0Request,
    RobotsTxtStatus,
    SiteClassification,
    SitemapStatus,
    UrlInventorySummary,
    WebsiteProfile,
)
from tr_seo_module0.openai_keyword_fallback import OpenAIKeywordFallbackService
from tr_seo_module0.semrush_client import FALLBACK_WARNING, SEMrushClient


def _request() -> Module0Request:
    return Module0Request(
        website_url="https://melbournegutterreplacements.com.au/",
        target_country="au",
        brand_name="Melbourne Gutter Replacements",
        business_type=BusinessType.SERVICE,
        services_or_products=["Gutter replacement", "Polycarbonate roofing"],
        target_locations=["Melbourne"],
        business_goals=["Increase leads"],
        priority_services=["Gutter replacement"],
    )


def _cdd() -> CDDExtraction:
    return CDDExtraction(
        text_preview="Direct competitors include Harley & Sons and https://guttersrusvic.com.au/",
        parser_used="csv",
        competitor_hints=[
            "Harley & Sons",
            "https://guttersrusvic.com.au/",
            "https://oboylesroofing.com.au/",
        ],
        detected_domains=[
            "guttersrusvic.com.au",
            "oboylesroofing.com.au",
        ],
    )


def _site_classification() -> SiteClassification:
    return SiteClassification(
        business_type=BusinessType.SERVICE,
        detected_domain="melbournegutterreplacements.com.au",
        cms="wordpress",
        site_scale_tier="<500",
    )


def _website_profile() -> WebsiteProfile:
    return WebsiteProfile(
        homepage_title="Melbourne Gutter Replacement | Gutter Repairs & Downpipes",
        meta_description="Gutter replacement, gutter repairs, and downpipe replacement across Melbourne.",
        homepage_text_excerpt=(
            "Melbourne gutter replacement specialists for gutter repairs, downpipe replacement, "
            "colorbond gutter installation, and emergency gutter repair."
        ),
        sample_page_titles=[
            "Gutter Replacement Melbourne",
            "Downpipe Replacement Melbourne",
            "Colorbond Gutter Installation",
        ],
        robots_txt=RobotsTxtStatus(url="https://melbournegutterreplacements.com.au/robots.txt"),
        sitemap=SitemapStatus(),
        url_inventory=UrlInventorySummary(
            sample_urls=["https://melbournegutterreplacements.com.au/services/gutter-replacement-melbourne"],
            service_like_urls=[
                "https://melbournegutterreplacements.com.au/services/gutter-replacement-melbourne",
                "https://melbournegutterreplacements.com.au/services/downpipe-replacement",
            ],
            location_like_urls=["https://melbournegutterreplacements.com.au/locations/melbourne"],
        ),
    )


def test_semrush_client_uses_deterministic_fallback_without_any_api_key() -> None:
    client = SEMrushClient(
        api_key=None,
        test_keyword_limit=5,
        openai_fallback_service=OpenAIKeywordFallbackService(api_key=None),
    )

    result = client.collect(_request(), cdd_extraction=_cdd())

    assert result.snapshot.fallback_used is True
    assert result.snapshot.warning_message == FALLBACK_WARNING
    assert result.snapshot.status == "credits_unavailable"
    assert result.snapshot.data_source == "mock_fallback"
    assert result.snapshot.is_estimated is True
    assert result.snapshot.keyword_limit == 5
    assert len(result.keywords) == 5
    assert len(result.competitors) > 0
    assert result.competitors[0].domain == "guttersrusvic.com.au"
    assert result.competitors[0].source in {"cdd_domain", "cdd_competitor_hint"}


def test_semrush_client_uses_manual_keyword_upload_before_mock_fallback() -> None:
    client = SEMrushClient(
        api_key=None,
        test_keyword_limit=200,
        openai_fallback_service=OpenAIKeywordFallbackService(api_key=None),
    )
    upload_meta = CDDFileMeta(
        filename="semrush-keywords.csv",
        content_type="text/csv",
        size_bytes=0,
        extension=".csv",
    )
    upload_body = """Keyword,Volume,KD,CPC,Position,URL
gutter replacement melbourne,880,34,8.1,6,https://melbournegutterreplacements.com.au/services/gutter-replacement
gutter repairs melbourne,590,29,7.2,8,https://melbournegutterreplacements.com.au/services/gutter-repairs
downpipe replacement melbourne,410,22,5.4,12,/services/downpipe-replacement
gutter replacement melbourne,880,34,8.1,6,https://melbournegutterreplacements.com.au/services/gutter-replacement
best gutter replacement near me company,220,19,4.0,14,https://melbournegutterreplacements.com.au/services/gutter-replacement
healthcare furniture melbourne,320,27,3.4,9,https://melbournegutterreplacements.com.au/collections/healthcare-furniture
"""

    result = client.collect(
        _request(),
        cdd_extraction=_cdd(),
        site_classification=_site_classification(),
        website_profile=_website_profile(),
        manual_keyword_file_meta=upload_meta,
        manual_keyword_content=upload_body.encode("utf-8"),
    )

    assert result.snapshot.data_source == "semrush_manual_upload"
    assert result.snapshot.status == "manual_upload"
    assert result.snapshot.fallback_used is True
    assert result.snapshot.is_estimated is False
    assert result.snapshot.raw_keyword_rows == 6
    assert result.snapshot.accepted_keyword_rows == 3
    assert result.snapshot.rejected_keyword_rows == 3
    assert all(item.source == "semrush_manual_upload" for item in result.keywords)
    assert [item.keyword for item in result.keywords] == [
        "gutter replacement melbourne",
        "gutter repair melbourne",
        "downpipe replacement melbourne",
    ]
    assert [item.mapped_url for item in result.keywords] == [
        "https://melbournegutterreplacements.com.au/services/gutter-replacement",
        "https://melbournegutterreplacements.com.au/services/gutter-repairs",
        "/services/downpipe-replacement",
    ]
    assert any("exact_duplicate" in item for item in result.snapshot.rejected_keyword_examples)
    assert "healthcare furniture melbourne" not in {item.keyword for item in result.keywords}


def test_semrush_client_prefers_live_semrush_over_manual_upload_when_api_works() -> None:
    upload_meta = CDDFileMeta(
        filename="semrush-keywords.csv",
        content_type="text/csv",
        size_bytes=0,
        extension=".csv",
    )
    upload_body = "Keyword,Volume,KD,CPC,Position\ngutter replacement melbourne,880,34,8.1,6\n"

    def handler(request: httpx.Request) -> httpx.Response:
        request_type = request.url.params.get("type")
        if request_type == "domain_rank":
            return httpx.Response(200, text="Dn;Ot;Or\nmelbournegutterreplacements.com.au;2400;18")
        if request_type == "domain_organic":
            return httpx.Response(
                200,
                text="Ph;Po;Nq;Kd;Cp\ngutter replacement melbourne;5;1000;31;8.5",
            )
        if request_type == "domain_organic_organic":
            return httpx.Response(
                200,
                text="Dn;Cr;Np\nguttersrusvic.com.au;0.67;44",
            )
        return httpx.Response(200, text="Ph;Po;Nq;Kd;Cp\ngutter replacement melbourne;4;900;28;7.9")

    client = SEMrushClient(
        api_key="semrush-test",
        test_keyword_limit=20,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        openai_fallback_service=OpenAIKeywordFallbackService(api_key=None),
    )

    result = client.collect(
        _request(),
        cdd_extraction=_cdd(),
        site_classification=_site_classification(),
        website_profile=_website_profile(),
        manual_keyword_file_meta=upload_meta,
        manual_keyword_content=upload_body.encode("utf-8"),
    )

    assert result.snapshot.data_source == "semrush"
    assert result.snapshot.fallback_used is False
    assert result.snapshot.source_file_name is None
    assert result.keywords[0].source == "semrush"


def test_semrush_client_uses_openai_estimated_fallback_when_available() -> None:
    keyword_rows = []
    for index in range(120):
        keyword_rows.append(
            {
                "keyword": f"gutter replacement melbourne {index}",
                "search_volume": 320 - (index % 40),
                "keyword_difficulty": 38 + (index % 12),
                "current_position": 10 + (index % 18),
                "cpc": 7.6 + ((index % 5) * 0.2),
                "intent": "transactional" if index % 3 else "informational",
                "priority": "P1" if index < 20 else "P2",
                "mapped_url": f"/services/gutter-replacement-{index}",
                "ai_answer_trigger_rate": 0.42,
                "confidence_score": 0.86,
                "quality_score": 0.88,
                "notes": ["Estimated by OpenAI fallback."],
            }
        )
    keyword_rows.extend(
        [
            {
                "keyword": "gutter replacement melbourne 0",
                "search_volume": 999,
                "keyword_difficulty": 99,
                "current_position": 1,
                "cpc": 20,
                "intent": "transactional",
                "priority": "P1",
                "mapped_url": "/services/duplicate",
                "ai_answer_trigger_rate": 0.9,
                "confidence_score": 0.9,
                "quality_score": 0.9,
                "notes": ["duplicate should be removed."],
            },
            {
                "keyword": "melbournegutterreplacements au company",
                "search_volume": 999,
                "keyword_difficulty": 10,
                "current_position": 3,
                "cpc": 10,
                "intent": "transactional",
                "priority": "P1",
                "mapped_url": "/services/bad-keyword",
                "ai_answer_trigger_rate": 0.4,
                "confidence_score": 0.4,
                "quality_score": 0.2,
                "notes": ["bad keyword should be removed."],
            },
            {
                "keyword": "melbournegutterreplacements.com.au gutter replacement",
                "search_volume": 120,
                "keyword_difficulty": 18,
                "current_position": 8,
                "cpc": 4.5,
                "intent": "transactional",
                "priority": "P2",
                "mapped_url": "/services/bad-domain-keyword",
                "ai_answer_trigger_rate": 0.3,
                "confidence_score": 0.3,
                "quality_score": 0.3,
                "notes": ["domain spam should be removed."],
            },
            {
                "keyword": "gutter replacement melbourne 80",
                "search_volume": 120,
                "keyword_difficulty": 18,
                "current_position": 8,
                "cpc": 4.5,
                "intent": "transactional",
                "priority": "P2",
                "mapped_url": "/services/bad-number-keyword",
                "ai_answer_trigger_rate": 0.3,
                "confidence_score": 0.3,
                "quality_score": 0.3,
                "notes": ["numeric suffix should be removed."],
            },
            {
                "keyword": "the essential role of rain gutter replacement in protecting melbourne homes",
                "search_volume": 190,
                "keyword_difficulty": 22,
                "current_position": 9,
                "cpc": 4.8,
                "intent": "informational",
                "priority": "P2",
                "mapped_url": "/resources/long-fragment",
                "ai_answer_trigger_rate": 0.4,
                "confidence_score": 0.81,
                "quality_score": 0.9,
                "notes": ["long scraped fragment should be removed."],
            },
            {
                "keyword": "gutters fascia downpipes small roofing installation gutters fascia downpipes",
                "search_volume": 140,
                "keyword_difficulty": 18,
                "current_position": 13,
                "cpc": 3.9,
                "intent": "transactional",
                "priority": "P2",
                "mapped_url": "/services/repeated-fragment",
                "ai_answer_trigger_rate": 0.35,
                "confidence_score": 0.77,
                "quality_score": 0.89,
                "notes": ["repeated token pattern should be removed."],
            },
            {
                "keyword": "rain gutter replacement roof gutter replacement melbourne consultation melbourne",
                "search_volume": 160,
                "keyword_difficulty": 20,
                "current_position": 11,
                "cpc": 4.1,
                "intent": "transactional",
                "priority": "P2",
                "mapped_url": "/services/near-duplicate-chain",
                "ai_answer_trigger_rate": 0.31,
                "confidence_score": 0.79,
                "quality_score": 0.9,
                "notes": ["duplicated terms should be removed."],
            },
            {
                "keyword": "roof gutter replacement melbourne estimate",
                "search_volume": 130,
                "keyword_difficulty": 21,
                "current_position": 10,
                "cpc": 4.0,
                "intent": "transactional",
                "priority": "P2",
                "mapped_url": "/services/low-quality-modifier",
                "ai_answer_trigger_rate": 0.28,
                "confidence_score": 0.74,
                "quality_score": 0.55,
                "notes": ["below quality threshold should be removed."],
            },
            {
                "keyword": "observed urls about gallery",
                "search_volume": 220,
                "keyword_difficulty": 14,
                "current_position": 6,
                "cpc": 2.2,
                "intent": "informational",
                "priority": "P2",
                "mapped_url": "/services/observed-urls-about-gallery",
                "ai_answer_trigger_rate": 0.2,
                "confidence_score": 0.82,
                "quality_score": 0.91,
                "notes": ["crawl artifact should be removed."],
            },
        ]
    )
    competitor_rows = [
        {
            "domain": "guttersrusvic.com.au",
            "name": "Gutters R Us Vic",
            "reason_for_selection": "Competes for gutter replacement services in Melbourne.",
            "likely_services": ["Gutter replacement", "Downpipes"],
            "content_gaps": ["Case studies", "FAQ depth"],
            "service_gaps": ["Polycarbonate roofing"],
            "estimated_strength": 74,
            "confidence_score": 0.81,
            "keyword_sample": ["gutter replacement melbourne", "downpipe replacement melbourne"],
            "notes": ["Derived from OpenAI fallback."],
        },
        {
            "domain": "oboylesroofing.com.au",
            "name": "O Boyles Roofing",
            "reason_for_selection": "Roofing and gutter competitor in the same geography.",
            "likely_services": ["Roof replacement", "Gutter replacement"],
            "content_gaps": ["Pricing pages"],
            "service_gaps": ["Patio roofing"],
            "estimated_strength": 79,
            "confidence_score": 0.78,
            "keyword_sample": ["roof gutter replacement melbourne"],
            "notes": ["Derived from OpenAI fallback."],
        },
        {
            "domain": "melbournegutterreplacements-competitor-1.com.au",
            "name": "Bad Placeholder",
            "reason_for_selection": "Should be filtered.",
            "likely_services": [],
            "content_gaps": [],
            "service_gaps": [],
            "estimated_strength": 20,
            "confidence_score": 0.1,
            "keyword_sample": [],
            "notes": [],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "keywords": keyword_rows,
                                    "competitors": competitor_rows,
                                    "notes": ["OpenAI estimated fallback keyword set generated."],
                                }
                            )
                        }
                    }
                ]
            },
        )

    openai_service = OpenAIKeywordFallbackService(
        api_key="openai-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client = SEMrushClient(
        api_key=None,
        test_keyword_limit=200,
        openai_fallback_service=openai_service,
    )

    result = client.collect(_request(), cdd_extraction=_cdd())

    assert result.snapshot.fallback_used is True
    assert result.snapshot.status == "credits_unavailable"
    assert result.snapshot.data_source == "openai_mock_fallback"
    assert result.snapshot.is_estimated is True
    assert result.snapshot.keyword_limit == 200
    assert 1 <= len(result.keywords) <= 200
    assert len({item.keyword for item in result.keywords}) == len(result.keywords)
    assert all("competitor-" not in item.domain for item in result.competitors)
    assert all(item.source == "openai_mock_fallback" for item in result.keywords)
    assert all(item.is_estimated is True for item in result.keywords)
    assert all(item.confidence_score > 0 for item in result.keywords)
    assert all(item.quality_score > 0 for item in result.keywords)
    assert all(item.search_volume > 0 for item in result.keywords)
    assert all(item.keyword_difficulty > 0 for item in result.keywords)
    assert all(item.cpc is not None and item.cpc > 0 for item in result.keywords)
    assert all(item.mapped_url for item in result.keywords)
    assert all("au company" not in item.keyword for item in result.keywords)
    assert all("melbournegutterreplacements" not in item.keyword for item in result.keywords)
    assert all(".com" not in item.keyword and ".au" not in item.keyword for item in result.keywords)
    assert all(not item.keyword.endswith(" 80") for item in result.keywords)
    assert all(
        len(item.keyword.split()) <= 8 or item.keyword.startswith(("how ", "what ", "why ", "who ", "where ", "when ", "is ", "do ", "does ", "can ", "should "))
        for item in result.keywords
    )
    assert all("the essential role of rain gutter replacement in protecting melbourne homes" != item.keyword for item in result.keywords)
    assert all("gutters fascia downpipes small roofing installation gutters fascia downpipes" != item.keyword for item in result.keywords)
    assert all("rain gutter replacement roof gutter replacement melbourne consultation melbourne" != item.keyword for item in result.keywords)
    assert all("roof gutter replacement melbourne estimate" != item.keyword for item in result.keywords)
    assert all("observed urls about gallery" != item.keyword for item in result.keywords)
    assert any(item.keyword == "gutter replacement melbourne" for item in result.keywords)
    assert result.competitors
    assert result.competitors[0].domain == "guttersrusvic.com.au"
    assert result.competitors[0].name == "Gutters R Us Vic"
    assert result.competitors[0].is_estimated is True
    assert result.competitors[0].confidence_score > 0
    assert result.competitors[0].estimated_strength > 0
    assert "OpenAI generated estimated fallback keyword data for this run." in result.snapshot.notes


def test_openai_fallback_recovers_keywords_from_context_when_model_output_is_noise() -> None:
    noisy_keywords = [
        {
            "keyword": "the essential role of rain gutter replacement in protecting melbourne homes",
            "quality_score": 0.95,
        },
        {
            "keyword": "gutters fascia downpipes small roofing installation gutters fascia downpipes",
            "quality_score": 0.95,
        },
        {
            "keyword": "rain gutter replacement roof gutter replacement melbourne consultation melbourne",
            "quality_score": 0.95,
        },
    ]
    competitor_rows = [
        {
            "domain": "guttersrusvic.com.au",
            "name": "Gutters R Us Vic",
            "reason_for_selection": "Competes for gutter replacement services in Melbourne.",
            "likely_services": ["Gutter replacement", "Downpipes"],
            "content_gaps": ["Pricing page"],
            "service_gaps": ["Commercial gutter replacement"],
            "estimated_strength": 74,
            "confidence_score": 0.81,
            "keyword_sample": [],
            "notes": ["Derived from OpenAI fallback."],
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "keywords": noisy_keywords,
                                    "competitors": competitor_rows,
                                    "notes": ["Noisy keyword rows should be filtered and recovered from context."],
                                }
                            )
                        }
                    }
                ]
            },
        )

    openai_service = OpenAIKeywordFallbackService(
        api_key="openai-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    request = _request().model_copy(
        update={
            "services_or_products": [],
            "priority_services": [],
            "business_type": BusinessType.UNKNOWN,
        }
    )
    client = SEMrushClient(
        api_key=None,
        test_keyword_limit=200,
        openai_fallback_service=openai_service,
    )

    result = client.collect(
        request,
        cdd_extraction=_cdd(),
        site_classification=_site_classification(),
        website_profile=_website_profile(),
    )

    assert result.snapshot.data_source == "openai_mock_fallback"
    assert result.keywords
    assert any("gutter" in item.keyword or "downpipe" in item.keyword for item in result.keywords)
    assert any(item.keyword == "gutter replacement melbourne" for item in result.keywords)
    assert all("the essential role of rain gutter replacement in protecting melbourne homes" != item.keyword for item in result.keywords)
    assert all("gutters fascia downpipes small roofing installation gutters fascia downpipes" != item.keyword for item in result.keywords)
    assert all("rain gutter replacement roof gutter replacement melbourne consultation melbourne" != item.keyword for item in result.keywords)
    assert all("quote pricing reviews" not in item.keyword for item in result.keywords)
    assert all("near me company" not in item.keyword for item in result.keywords)
    assert all("locations melbourne" not in item.keyword for item in result.keywords)
    assert all("observed urls about gallery" not in item.keyword for item in result.keywords)
    assert all(
        len(item.keyword.split()) <= 8
        or item.keyword.startswith(("how ", "what ", "why ", "who ", "where ", "when ", "is ", "do ", "does ", "can ", "should "))
        for item in result.keywords
    )


def test_openai_fallback_filters_context_irrelevant_service_noise() -> None:
    raw_keywords = [
        {
            "keyword": "much fascia replacement",
            "quality_score": 0.91,
            "intent": "transactional",
            "priority": "P1",
        },
        {
            "keyword": "observed urls about gallery",
            "quality_score": 0.92,
            "intent": "informational",
            "priority": "P2",
        },
        {
            "keyword": "downpipe replacement melbourne",
            "quality_score": 0.89,
            "intent": "transactional",
            "priority": "P1",
        },
    ]
    competitor_rows = [
        {
            "domain": "guttersrusvic.com.au",
            "name": "Gutters R Us Vic",
            "reason_for_selection": "Competes for gutter replacement services in Melbourne.",
            "likely_services": ["Gutter replacement", "Downpipes"],
            "content_gaps": ["Pricing page"],
            "service_gaps": ["Commercial gutter replacement"],
            "estimated_strength": 74,
            "confidence_score": 0.81,
            "keyword_sample": [],
            "notes": ["Derived from OpenAI fallback."],
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "keywords": raw_keywords,
                                    "competitors": competitor_rows,
                                    "notes": ["Context relevance filtering should retain only real business queries."],
                                }
                            )
                        }
                    }
                ]
            },
        )

    openai_service = OpenAIKeywordFallbackService(
        api_key="openai-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client = SEMrushClient(
        api_key=None,
        test_keyword_limit=50,
        openai_fallback_service=openai_service,
    )

    result = client.collect(
        _request(),
        cdd_extraction=_cdd(),
        site_classification=_site_classification(),
        website_profile=_website_profile(),
    )

    assert result.keywords
    assert all(item.keyword != "much fascia replacement" for item in result.keywords)
    assert all(item.keyword != "observed urls about gallery" for item in result.keywords)
    assert any(item.keyword == "downpipe replacement melbourne" for item in result.keywords)


def test_semrush_client_uses_live_data_when_api_works() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        report_type = request.url.params["type"]
        if report_type == "domain_rank":
            return httpx.Response(200, text="Dn;Ot;Or\nmelbournegutterreplacements.com.au;321;45\n")
        if report_type == "domain_organic":
            return httpx.Response(
                200,
                text=(
                    "Ph;Po;Nq;Kd;Cp\n"
                    "gutter replacement melbourne;7;210;24;4.2\n"
                    "polycarbonate roofing melbourne;12;170;28;5.8\n"
                    "roof gutter replacement;19;90;33;3.6\n"
                ),
            )
        if report_type == "domain_organic_organic":
            return httpx.Response(
                200,
                text="Dn;Cr;Np\ncompetitor-a.com.au;0.81;34\ncompetitor-b.com.au;0.64;22\n",
            )
        raise AssertionError(f"Unexpected report type: {report_type}")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = SEMrushClient(api_key="test-key", test_keyword_limit=2, http_client=http_client)

    result = client.collect(_request())

    assert result.snapshot.fallback_used is False
    assert result.snapshot.data_source == "semrush"
    assert result.snapshot.status == "live"
    assert result.snapshot.is_estimated is False
    assert result.snapshot.estimated_monthly_traffic == 321
    assert result.snapshot.keyword_limit == 2
    assert len(result.keywords) == 2
    assert result.keywords[0].keyword == "gutter replacement melbourne"
    assert result.keywords[0].is_estimated is False


def test_semrush_client_falls_back_on_credit_style_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ERROR 50 :: NOT_ENOUGH_UNITS")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = SEMrushClient(
        api_key="test-key",
        test_keyword_limit=4,
        http_client=http_client,
        openai_fallback_service=OpenAIKeywordFallbackService(api_key=None),
    )

    result = client.collect(_request())

    assert result.snapshot.fallback_used is True
    assert result.snapshot.warning_message == FALLBACK_WARNING
    assert result.snapshot.status == "credits_unavailable"
    assert "Fallback reason: credits." in result.snapshot.notes
