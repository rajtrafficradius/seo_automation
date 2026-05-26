import json

import httpx

from tr_seo_contracts.module0 import (
    CompetitorRecord,
    EntityAuthorityBaseline,
    EntityMention,
    FanOutKeywordMap,
    FanOutMap,
    FanOutSubQuery,
    KeywordIntent,
    KeywordOpportunity,
    KeywordPriority,
    Module0Request,
    WebsiteProfile,
    RobotsTxtStatus,
    SitemapStatus,
    UrlInventorySummary,
)
from tr_seo_module0.ai_sov import AISOVService


def _request() -> Module0Request:
    return Module0Request(
        website_url="https://melbournegutterreplacements.com.au/",
        target_country="au",
        brand_name="Melbourne Gutter Replacements",
        services_or_products=["Gutter replacement", "Gutter repairs", "Downpipe replacement"],
        target_locations=["Melbourne"],
        business_goals=["Increase leads", "Improve AI visibility"],
        priority_services=["Gutter replacement"],
        brand_profiles=["https://www.facebook.com/example"],
    )


def _website_profile() -> WebsiteProfile:
    return WebsiteProfile(
        homepage_title="Melbourne Gutter Replacement and Gutter Repairs",
        meta_description="Gutter replacement, repairs, and downpipe replacement across Melbourne.",
        homepage_text_excerpt=(
            "Local gutter replacement specialists offering gutter repairs, downpipe replacement, "
            "and Colorbond gutter installation across Melbourne."
        ),
        detected_schema_types=["Organization", "LocalBusiness", "Service"],
        social_profile_links=["https://www.facebook.com/example"],
        sample_page_titles=[
            "Gutter Replacement Melbourne",
            "Gutter Repairs Melbourne",
            "Downpipe Replacement Melbourne",
        ],
        robots_txt=RobotsTxtStatus(url="https://melbournegutterreplacements.com.au/robots.txt"),
        sitemap=SitemapStatus(),
        url_inventory=UrlInventorySummary(
            sample_urls=["https://melbournegutterreplacements.com.au/services/gutter-replacement-melbourne"],
        ),
    )


def _keywords() -> list[KeywordOpportunity]:
    return [
        KeywordOpportunity(
            keyword="gutter replacement melbourne",
            intent=KeywordIntent.TRANSACTIONAL,
            priority=KeywordPriority.P1,
            search_volume=260,
            keyword_difficulty=31,
            mapped_url="/services/gutter-replacement-melbourne",
            ai_answer_trigger_rate=0.58,
            confidence_score=0.84,
            quality_score=0.9,
            is_estimated=True,
        ),
        KeywordOpportunity(
            keyword="gutter replacement cost melbourne",
            intent=KeywordIntent.INFORMATIONAL,
            priority=KeywordPriority.P1,
            search_volume=180,
            keyword_difficulty=28,
            mapped_url="/services/gutter-replacement-melbourne",
            ai_answer_trigger_rate=0.82,
            confidence_score=0.8,
            quality_score=0.88,
            is_estimated=True,
        ),
        KeywordOpportunity(
            keyword="emergency gutter repair",
            intent=KeywordIntent.TRANSACTIONAL,
            priority=KeywordPriority.P1,
            search_volume=120,
            keyword_difficulty=24,
            mapped_url="/services/emergency-gutter-repair",
            ai_answer_trigger_rate=0.61,
            confidence_score=0.77,
            quality_score=0.86,
            is_estimated=True,
        ),
    ]


def _competitors() -> list[CompetitorRecord]:
    return [
        CompetitorRecord(
            domain="guttersrusvic.com.au",
            name="Gutters R Us Vic",
            source="estimated",
            reason_for_selection="Overlapping gutter replacement services in Melbourne.",
            likely_services=["Gutter replacement", "Downpipes"],
            content_gaps=["FAQ depth"],
            service_gaps=["Emergency repair"],
            estimated_strength=74,
            confidence_score=0.82,
            is_estimated=True,
        ),
        CompetitorRecord(
            domain="oboylesroofing.com.au",
            name="O'Boyles Roofing",
            source="estimated",
            reason_for_selection="Roofing and gutter competitor in the same geography.",
            likely_services=["Roof repairs", "Gutter replacement"],
            content_gaps=["Pricing detail"],
            service_gaps=["Commercial gutter replacement"],
            estimated_strength=71,
            confidence_score=0.77,
            is_estimated=True,
        ),
    ]


def _fan_out() -> FanOutMap:
    return FanOutMap(
        methodology="test",
        average_coverage=0.42,
        keyword_maps=[
            FanOutKeywordMap(
                root_keyword="gutter replacement cost melbourne",
                coverage_score=0.3,
                invisible_keywords=["gutter replacement price", "how much does gutter replacement cost"],
                sub_queries=[
                    FanOutSubQuery(query="how much does gutter replacement cost", content_requirement="FAQ answer"),
                ],
            )
        ],
    )


def _entity() -> EntityAuthorityBaseline:
    return EntityAuthorityBaseline(
        score=58,
        knowledge_panel_status="not_verified",
        same_as_links=["https://www.facebook.com/example"],
        brand_mentions=[EntityMention(source_name="Facebook", mention_type="social", consistent=True)],
        consistency_gaps=["Limited third-party mentions"],
        reinforcement_opportunities=["Add more branded service citations"],
        methodology="test",
    )


def test_ai_sov_service_uses_openai_assisted_estimation() -> None:
    payload = {
        "overall_ai_sov_score": 0.47,
        "brand_visibility_summary": "The brand has moderate estimated visibility for local gutter replacement queries but weaker coverage for cost-led and emergency questions.",
        "competitor_visibility_comparison": [
            {
                "domain": "guttersrusvic.com.au",
                "name": "Gutters R Us Vic",
                "likely_visibility_score": 0.63,
                "summary": "Likely cited for core gutter replacement and repair topics.",
                "confidence_score": 0.78,
            }
        ],
        "ai_answer_triggering_keywords": [
            "gutter replacement cost melbourne",
            "emergency gutter repair",
        ],
        "missing_visibility_opportunities": [
            "gutter replacement cost melbourne",
            "how much does gutter replacement cost",
        ],
        "recommended_geo_aeo_actions": [
            "Add a Melbourne gutter replacement cost FAQ with concise answers and pricing ranges.",
            "Strengthen LocalBusiness and Service schema on gutter replacement pages.",
        ],
        "citation_likelihood_by_keyword": [
            {
                "keyword": "gutter replacement melbourne",
                "citation_likelihood_score": 0.52,
                "reason": "Strong local service relevance but competitor entity signals are stronger.",
                "confidence_score": 0.74,
            }
        ],
        "confidence_score": 0.73,
        "engine_results": [
            {
                "engine": "google_ai_overviews",
                "target_queries": 3,
                "cited_queries": 1,
                "score": 0.41,
                "notes": ["Estimated, not live measured."],
            },
            {
                "engine": "perplexity",
                "target_queries": 3,
                "cited_queries": 2,
                "score": 0.5,
                "notes": ["Estimated, not live measured."],
            },
        ],
        "query_results": [
            {
                "engine": "google_ai_overviews",
                "query": "gutter replacement melbourne",
                "keyword": "gutter replacement melbourne",
                "keyword_intent": "transactional",
                "brand_likely_cited": False,
                "competitors_likely_cited": ["guttersrusvic.com.au"],
                "reason": "Competitor topical authority is currently stronger for the core service query.",
                "citation_likelihood_score": 0.44,
                "confidence_score": 0.76,
                "content_gap": "Needs stronger location-specific proof and answer-focused sections.",
                "recommended_content_action": "Improve the core gutter replacement page with concise answer blocks.",
                "citation_domains": ["guttersrusvic.com.au"],
                "notes": ["Estimated with OpenAI reasoning."],
            }
        ],
        "methodology_notes": ["Use this as an estimated fallback only."],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    service = AISOVService(
        api_key="openai-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = service.build(
        keywords=_keywords(),
        brand_name="Melbourne Gutter Replacements",
        request=_request(),
        website_profile=_website_profile(),
        competitors=_competitors(),
        fan_out_map=_fan_out(),
        entity_authority_baseline=_entity(),
    )

    assert result.status == "openai_estimated"
    assert result.overall_ai_sov_score > 0
    assert result.brand_visibility_summary
    assert result.competitor_visibility_comparison
    assert result.ai_answer_triggering_keywords
    assert result.missing_visibility_opportunities
    assert result.recommended_geo_aeo_actions
    assert result.citation_likelihood_by_keyword
    assert result.confidence_score > 0
    assert result.query_results
    assert result.query_results[0].query == "gutter replacement melbourne"
    assert result.query_results[0].recommended_content_action
    assert result.query_results[0].content_gap


def test_ai_sov_service_returns_structured_estimate_without_openai() -> None:
    service = AISOVService(api_key=None)

    result = service.build(
        keywords=_keywords(),
        brand_name="Melbourne Gutter Replacements",
        request=_request(),
        website_profile=_website_profile(),
        competitors=_competitors(),
        fan_out_map=_fan_out(),
        entity_authority_baseline=_entity(),
    )

    assert result.status in {"heuristic_estimated", "openai_estimated_fallback_failed"}
    assert result.overall_ai_sov_score > 0
    assert result.brand_visibility_summary
    assert result.query_results
    assert result.citation_likelihood_by_keyword
    assert result.recommended_geo_aeo_actions
