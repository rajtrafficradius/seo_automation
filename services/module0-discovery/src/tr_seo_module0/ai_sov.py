from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from tr_seo_contracts.module0 import (
    AISOVBaseline,
    AISOVCitationLikelihood,
    AISOVCompetitorVisibility,
    AISOVEngineResult,
    AISOVQueryResult,
    CompetitorRecord,
    EntityAuthorityBaseline,
    FanOutMap,
    KeywordIntent,
    KeywordOpportunity,
    Module0Request,
    WebsiteProfile,
)


class OpenAIAISOVError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class AISOVService:
    ENGINES = ["google_ai_overviews", "perplexity", "chatgpt"]
    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.http_client = http_client

    def build(
        self,
        keywords: list[KeywordOpportunity],
        brand_name: str,
        request: Module0Request | None = None,
        website_profile: WebsiteProfile | None = None,
        competitors: list[CompetitorRecord] | None = None,
        fan_out_map: FanOutMap | None = None,
        entity_authority_baseline: EntityAuthorityBaseline | None = None,
    ) -> AISOVBaseline:
        candidate_keywords = self._select_candidate_keywords(keywords, fan_out_map)
        competitors = competitors or []
        entity_authority_baseline = entity_authority_baseline or EntityAuthorityBaseline(methodology="No entity evidence provided.")

        if self.api_key and candidate_keywords:
            try:
                return self._build_openai_estimate(
                    candidate_keywords=candidate_keywords,
                    brand_name=brand_name,
                    request=request,
                    website_profile=website_profile,
                    competitors=competitors,
                    fan_out_map=fan_out_map,
                    entity_authority_baseline=entity_authority_baseline,
                )
            except OpenAIAISOVError as error:
                return self._build_estimated_baseline(
                    candidate_keywords,
                    brand_name=brand_name,
                    request=request,
                    website_profile=website_profile,
                    competitors=competitors,
                    fan_out_map=fan_out_map,
                    entity_authority_baseline=entity_authority_baseline,
                    status="openai_estimated_fallback_failed",
                    methodology_note=f"OpenAI-assisted AI SOV estimation failed: {error.reason}. {error.message}",
                )

        return self._build_estimated_baseline(
            candidate_keywords,
            brand_name=brand_name,
            request=request,
            website_profile=website_profile,
            competitors=competitors,
            fan_out_map=fan_out_map,
            entity_authority_baseline=entity_authority_baseline,
            status="heuristic_estimated",
            methodology_note=(
                "OpenAI-assisted AI SOV estimation was not available, so a structured estimated baseline "
                "was generated from keyword universe, site signals, competitors, fan-out opportunities, "
                "and entity authority."
            ),
        )

    def _build_openai_estimate(
        self,
        candidate_keywords: list[KeywordOpportunity],
        brand_name: str,
        request: Module0Request | None,
        website_profile: WebsiteProfile | None,
        competitors: list[CompetitorRecord],
        fan_out_map: FanOutMap | None,
        entity_authority_baseline: EntityAuthorityBaseline,
    ) -> AISOVBaseline:
        payload = self._build_payload(
            candidate_keywords,
            brand_name,
            request,
            website_profile,
            competitors,
            fan_out_map,
            entity_authority_baseline,
        )
        try:
            with self._get_client() as client:
                response = client.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise OpenAIAISOVError("timeout", "OpenAI AI SOV request timed out.") from error
        except httpx.HTTPStatusError as error:
            raise OpenAIAISOVError(
                "api_access_error",
                f"OpenAI AI SOV returned HTTP {error.response.status_code}.",
            ) from error
        except httpx.HTTPError as error:
            raise OpenAIAISOVError("api_access_error", "OpenAI AI SOV request failed.") from error

        body = response.json()
        content = self._extract_content(body)
        if not content:
            raise OpenAIAISOVError("empty_response", "OpenAI AI SOV returned no content.")
        try:
            parsed = json.loads(self._strip_code_fence(content))
        except json.JSONDecodeError as error:
            raise OpenAIAISOVError("invalid_json", "OpenAI AI SOV returned invalid JSON.") from error

        engine_results = self._parse_engine_results(parsed.get("engine_results", []))
        query_results = self._parse_query_results(parsed.get("query_results", []), candidate_keywords, competitors)
        if not query_results:
            raise OpenAIAISOVError("empty_queries", "OpenAI AI SOV returned no query-level estimates.")

        competitor_visibility = self._parse_competitor_visibility(
            parsed.get("competitor_visibility_comparison", []),
            competitors,
        )
        citation_likelihood = self._parse_citation_likelihood(
            parsed.get("citation_likelihood_by_keyword", []),
            candidate_keywords,
            query_results,
        )

        overall_score = self._coerce_probability(
            parsed.get("overall_ai_sov_score"),
            default=self._average([item.score for item in engine_results]) or self._average(
                [item.citation_likelihood_score for item in query_results]
            ),
        )
        if not engine_results:
            engine_results = self._synthesize_engine_results(query_results, overall_score, status="openai_estimated")

        missing_keywords = self._clean_string_list(parsed.get("missing_visibility_opportunities", []), 15)
        if not missing_keywords:
            missing_keywords = [item.query for item in query_results if not item.brand_likely_cited][:10]

        ai_triggering_keywords = self._clean_string_list(parsed.get("ai_answer_triggering_keywords", []), 12)
        if not ai_triggering_keywords:
            ai_triggering_keywords = [
                item.keyword
                for item in candidate_keywords
                if (item.ai_answer_trigger_rate or 0) >= 0.55 or item.intent == KeywordIntent.INFORMATIONAL
            ][:12]

        summary = str(parsed.get("brand_visibility_summary", "")).strip()
        if not summary:
            summary = self._default_brand_visibility_summary(
                overall_score,
                brand_name,
                query_results,
                competitor_visibility,
            )

        actions = self._clean_string_list(parsed.get("recommended_geo_aeo_actions", []), 12)
        if not actions:
            actions = self._default_recommended_actions(query_results, request, website_profile)

        confidence_score = self._coerce_probability(
            parsed.get("confidence_score"),
            default=self._average([item.confidence_score for item in query_results]) or 0.62,
        )

        methodology_notes = self._clean_string_list(parsed.get("methodology_notes", []), 6)
        methodology = (
            "OpenAI-assisted hybrid AI SOV estimation using keyword universe, website profile, "
            "location context, competitor set, fan-out opportunities, and entity authority baseline. "
            "This is an estimated fallback, not live provider-measured AI SOV."
        )
        if methodology_notes:
            methodology = f"{methodology} {' '.join(methodology_notes)}"

        return AISOVBaseline(
            overall_score=overall_score,
            overall_ai_sov_score=overall_score,
            status="openai_estimated",
            methodology=methodology,
            brand_visibility_summary=summary,
            competitor_visibility_comparison=competitor_visibility,
            ai_answer_triggering_keywords=ai_triggering_keywords,
            missing_visibility_opportunities=missing_keywords,
            recommended_geo_aeo_actions=actions,
            citation_likelihood_by_keyword=citation_likelihood,
            confidence_score=confidence_score,
            engine_results=engine_results,
            query_results=query_results,
            missing_visibility_keywords=missing_keywords,
        )

    def _build_estimated_baseline(
        self,
        candidate_keywords: list[KeywordOpportunity],
        brand_name: str,
        request: Module0Request | None,
        website_profile: WebsiteProfile | None,
        competitors: list[CompetitorRecord],
        fan_out_map: FanOutMap | None,
        entity_authority_baseline: EntityAuthorityBaseline,
        status: str,
        methodology_note: str,
    ) -> AISOVBaseline:
        entity_factor = min(entity_authority_baseline.score / 100, 1.0)
        competitor_visibility = self._default_competitor_visibility(competitors)

        query_results: list[AISOVQueryResult] = []
        for keyword in candidate_keywords[:12]:
            competitors_likely_cited = [item.domain for item in competitors[: min(len(competitors), 3)]]
            citation_score = self._estimated_query_score(keyword, entity_factor, request, website_profile)
            brand_likely_cited = citation_score >= 0.56
            content_gap = self._derive_content_gap(keyword, fan_out_map, website_profile)
            action = self._derive_content_action(keyword, request)
            reason = self._derive_reason(keyword, brand_name, competitors_likely_cited, entity_factor, website_profile)
            query_results.append(
                AISOVQueryResult(
                    engine="hybrid_estimate",
                    query=keyword.keyword,
                    keyword=keyword.keyword,
                    keyword_intent=keyword.intent,
                    brand_likely_cited=brand_likely_cited,
                    cited=brand_likely_cited,
                    competitors_likely_cited=competitors_likely_cited,
                    competitor_cited=competitors_likely_cited,
                    citation_domains=[],
                    reason=reason,
                    citation_likelihood_score=citation_score,
                    confidence_score=max(keyword.confidence_score, 0.55),
                    confidence=max(keyword.confidence_score, 0.55),
                    content_gap=content_gap,
                    recommended_content_action=action,
                    notes=[
                        "Estimated AI SOV query-level judgment generated without live provider probing.",
                    ],
                )
            )

        overall_score = self._average([item.citation_likelihood_score for item in query_results]) or 0.22
        engine_results = self._synthesize_engine_results(query_results, overall_score, status=status)
        missing_keywords = [item.query for item in query_results if not item.brand_likely_cited][:10]
        ai_triggering_keywords = [
            item.keyword
            for item in candidate_keywords
            if (item.ai_answer_trigger_rate or 0) >= 0.55 or item.intent == KeywordIntent.INFORMATIONAL
        ][:12]
        actions = self._default_recommended_actions(query_results, request, website_profile)
        citation_likelihood = [
            AISOVCitationLikelihood(
                keyword=item.keyword,
                citation_likelihood_score=item.citation_likelihood_score,
                reason=item.reason,
                confidence_score=item.confidence_score,
            )
            for item in query_results[:12]
        ]

        return AISOVBaseline(
            overall_score=overall_score,
            overall_ai_sov_score=overall_score,
            status=status,
            methodology=(
                f"{methodology_note} This is not live measured AI SOV; it is a structured estimate from "
                "brand, site, keyword, competitor, fan-out, and entity signals."
            ),
            brand_visibility_summary=self._default_brand_visibility_summary(
                overall_score,
                brand_name,
                query_results,
                competitor_visibility,
            ),
            competitor_visibility_comparison=competitor_visibility,
            ai_answer_triggering_keywords=ai_triggering_keywords,
            missing_visibility_opportunities=missing_keywords,
            recommended_geo_aeo_actions=actions,
            citation_likelihood_by_keyword=citation_likelihood,
            confidence_score=self._average([item.confidence_score for item in query_results]) or 0.58,
            engine_results=engine_results,
            query_results=query_results,
            missing_visibility_keywords=missing_keywords,
        )

    def _build_payload(
        self,
        candidate_keywords: list[KeywordOpportunity],
        brand_name: str,
        request: Module0Request | None,
        website_profile: WebsiteProfile | None,
        competitors: list[CompetitorRecord],
        fan_out_map: FanOutMap | None,
        entity_authority_baseline: EntityAuthorityBaseline,
    ) -> dict[str, Any]:
        brand_profiles = request.brand_profiles if request else []
        competitor_payload = [
            {
                "domain": item.domain,
                "name": item.name,
                "reason_for_selection": item.reason_for_selection,
                "likely_services": item.likely_services,
                "content_gaps": item.content_gaps,
                "service_gaps": item.service_gaps,
                "estimated_strength": item.estimated_strength,
                "confidence_score": item.confidence_score,
            }
            for item in competitors[:6]
        ]
        fan_out_payload = []
        if fan_out_map:
            for item in fan_out_map.keyword_maps[:10]:
                fan_out_payload.append(
                    {
                        "root_keyword": item.root_keyword,
                        "invisible_keywords": item.invisible_keywords[:5],
                        "coverage_score": item.coverage_score,
                    }
                )
        keyword_payload = [
            {
                "keyword": item.keyword,
                "intent": item.intent.value,
                "priority": item.priority.value,
                "search_volume": item.search_volume,
                "keyword_difficulty": item.keyword_difficulty,
                "mapped_url": item.mapped_url,
                "ai_answer_trigger_rate": item.ai_answer_trigger_rate,
                "confidence_score": item.confidence_score,
                "quality_score": item.quality_score,
            }
            for item in candidate_keywords[:12]
        ]

        system_prompt = (
            "You are estimating AI Share of Voice for a local SEO system when live provider data is unavailable. "
            "Return only valid JSON. Do not claim real measured AI SOV. Use realistic reasoning grounded in "
            "brand, website content, location, services, keyword universe, competitors, query fan-out, and "
            "entity authority. Avoid generic statements. Scores should be plausible and non-zero unless there is "
            "a clear reason."
        )
        user_payload = {
            "task": "Generate an OpenAI-assisted estimated AI SOV baseline for Module 0.",
            "requirements": {
                "brand_name": brand_name,
                "target_country": request.target_country if request else None,
                "target_locations": request.target_locations if request else [],
                "services_or_products": request.services_or_products if request else [],
                "business_goals": request.business_goals if request else [],
                "brand_profiles": brand_profiles,
                "website_title": website_profile.homepage_title if website_profile else None,
                "website_meta_description": website_profile.meta_description if website_profile else None,
                "website_content_summary": website_profile.homepage_text_excerpt if website_profile else None,
                "sample_page_titles": website_profile.sample_page_titles if website_profile else [],
                "sample_urls": website_profile.url_inventory.sample_urls[:8] if website_profile else [],
                "keyword_universe": keyword_payload,
                "competitors": competitor_payload,
                "fan_out_opportunities": fan_out_payload,
                "entity_authority": {
                    "score": entity_authority_baseline.score,
                    "knowledge_panel_status": entity_authority_baseline.knowledge_panel_status,
                    "same_as_links": entity_authority_baseline.same_as_links,
                    "consistency_gaps": entity_authority_baseline.consistency_gaps,
                    "reinforcement_opportunities": entity_authority_baseline.reinforcement_opportunities,
                },
                "rules": [
                    "Estimate likely AI visibility for Google AI Overviews, Perplexity, and ChatGPT.",
                    "Do not claim real provider-measured AI SOV.",
                    "Avoid generic explanations.",
                    "Use specific competitors and specific missing opportunities.",
                    "Do not return only zero scores unless there is a strong reason from the input evidence.",
                ],
            },
            "output_schema": {
                "overall_ai_sov_score": "number 0-1",
                "brand_visibility_summary": "string",
                "competitor_visibility_comparison": [
                    {
                        "domain": "string",
                        "name": "string",
                        "likely_visibility_score": "number 0-1",
                        "summary": "string",
                        "confidence_score": "number 0-1",
                    }
                ],
                "ai_answer_triggering_keywords": ["string"],
                "missing_visibility_opportunities": ["string"],
                "recommended_geo_aeo_actions": ["string"],
                "citation_likelihood_by_keyword": [
                    {
                        "keyword": "string",
                        "citation_likelihood_score": "number 0-1",
                        "reason": "string",
                        "confidence_score": "number 0-1",
                    }
                ],
                "confidence_score": "number 0-1",
                "engine_results": [
                    {
                        "engine": "google_ai_overviews | perplexity | chatgpt",
                        "target_queries": "integer",
                        "cited_queries": "integer",
                        "score": "number 0-1",
                        "notes": ["string"],
                    }
                ],
                "query_results": [
                    {
                        "engine": "google_ai_overviews | perplexity | chatgpt | hybrid_estimate",
                        "query": "string",
                        "keyword": "string",
                        "keyword_intent": "transactional | navigational_aeo | informational",
                        "brand_likely_cited": "boolean",
                        "competitors_likely_cited": ["string"],
                        "reason": "string",
                        "citation_likelihood_score": "number 0-1",
                        "confidence_score": "number 0-1",
                        "content_gap": "string",
                        "recommended_content_action": "string",
                        "citation_domains": ["string"],
                        "notes": ["string"],
                    }
                ],
                "methodology_notes": ["string"],
            },
        }

        return {
            "model": self.model,
            "temperature": 0.15,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        }

    def _select_candidate_keywords(
        self,
        keywords: list[KeywordOpportunity],
        fan_out_map: FanOutMap | None,
    ) -> list[KeywordOpportunity]:
        ranked = sorted(
            keywords,
            key=lambda item: (
                {"P1": 0, "P2": 1, "P3": 2}.get(item.priority.value, 3),
                -(item.ai_answer_trigger_rate or 0.0),
                -item.search_volume,
                -item.quality_score,
            ),
        )
        selected: list[KeywordOpportunity] = []
        seen: set[str] = set()
        for item in ranked:
            normalized = item.keyword.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            selected.append(item)
            if len(selected) >= 12:
                break
        if fan_out_map:
            for item in fan_out_map.keyword_maps:
                if len(selected) >= 12:
                    break
                if item.root_keyword.strip().lower() in seen:
                    continue
                seen.add(item.root_keyword.strip().lower())
                selected.append(
                    KeywordOpportunity(
                        keyword=item.root_keyword,
                        intent=KeywordIntent.INFORMATIONAL,
                        priority=next((row.priority for row in ranked if row.keyword == item.root_keyword), None) or ranked[0].priority if ranked else None,  # type: ignore[arg-type]
                        search_volume=0,
                        keyword_difficulty=0,
                        source="fanout-root",
                        ai_answer_trigger_rate=item.coverage_score,
                        confidence_score=0.55,
                        quality_score=0.6,
                        is_estimated=True,
                    )
                )
        return selected[:12]

    def _parse_engine_results(self, values: list[dict[str, Any]]) -> list[AISOVEngineResult]:
        results: list[AISOVEngineResult] = []
        for item in values:
            engine = str(item.get("engine", "")).strip().lower()
            if engine not in self.ENGINES:
                continue
            score = self._coerce_probability(item.get("score"), default=0.0)
            target_queries = max(self._to_int(item.get("target_queries")), 0)
            cited_queries = max(min(self._to_int(item.get("cited_queries")), target_queries or 0), 0)
            results.append(
                AISOVEngineResult(
                    engine=engine,
                    status="openai_estimated",
                    target_queries=target_queries,
                    cited_queries=cited_queries,
                    score=score,
                    notes=self._clean_string_list(item.get("notes", []), 5),
                )
            )
        return results

    def _parse_query_results(
        self,
        values: list[dict[str, Any]],
        candidate_keywords: list[KeywordOpportunity],
        competitors: list[CompetitorRecord],
    ) -> list[AISOVQueryResult]:
        keyword_lookup = {item.keyword.lower(): item for item in candidate_keywords}
        competitor_lookup = {item.domain: item for item in competitors}
        results: list[AISOVQueryResult] = []
        seen: set[tuple[str, str]] = set()
        for item in values:
            query = self._clean_text(item.get("query") or item.get("keyword"))
            if not query:
                continue
            engine = str(item.get("engine", "hybrid_estimate")).strip().lower() or "hybrid_estimate"
            if engine not in {*self.ENGINES, "hybrid_estimate"}:
                engine = "hybrid_estimate"
            key = (engine, query.lower())
            if key in seen:
                continue
            seen.add(key)
            keyword_model = keyword_lookup.get(query.lower())
            intent = self._normalize_intent(
                item.get("keyword_intent"),
                keyword_model.intent if keyword_model else None,
            )
            competitors_likely_cited = self._clean_string_list(item.get("competitors_likely_cited", []), 4)
            if not competitors_likely_cited:
                competitors_likely_cited = [row.domain for row in competitors[: min(len(competitors), 3)]]
            confidence_score = self._coerce_probability(
                item.get("confidence_score"),
                default=max(keyword_model.confidence_score, 0.58) if keyword_model else 0.58,
            )
            citation_score = self._coerce_probability(
                item.get("citation_likelihood_score"),
                default=(keyword_model.ai_answer_trigger_rate or 0.35) if keyword_model else 0.35,
            )
            brand_likely_cited = bool(item.get("brand_likely_cited")) or citation_score >= 0.56
            citation_domains = self._clean_string_list(item.get("citation_domains", []), 5)
            if not citation_domains:
                citation_domains = [competitor_lookup[domain].domain for domain in competitors_likely_cited if domain in competitor_lookup][:3]
            results.append(
                AISOVQueryResult(
                    engine=engine,
                    query=query,
                    keyword=query,
                    keyword_intent=intent,
                    brand_likely_cited=brand_likely_cited,
                    cited=brand_likely_cited,
                    competitors_likely_cited=competitors_likely_cited,
                    competitor_cited=competitors_likely_cited,
                    citation_domains=citation_domains,
                    reason=self._clean_text(item.get("reason")),
                    citation_likelihood_score=citation_score,
                    confidence_score=confidence_score,
                    confidence=confidence_score,
                    content_gap=self._clean_text(item.get("content_gap")),
                    recommended_content_action=self._clean_text(item.get("recommended_content_action")),
                    notes=self._clean_string_list(item.get("notes", []), 5),
                )
            )
        return results

    def _parse_competitor_visibility(
        self,
        values: list[dict[str, Any]],
        competitors: list[CompetitorRecord],
    ) -> list[AISOVCompetitorVisibility]:
        parsed: list[AISOVCompetitorVisibility] = []
        seen: set[str] = set()
        for item in values:
            domain = self._clean_text(item.get("domain")).lower()
            if not domain or domain in seen:
                continue
            seen.add(domain)
            parsed.append(
                AISOVCompetitorVisibility(
                    domain=domain,
                    name=self._clean_text(item.get("name")) or self._name_from_domain(domain),
                    likely_visibility_score=self._coerce_probability(item.get("likely_visibility_score"), default=0.45),
                    summary=self._clean_text(item.get("summary")),
                    confidence_score=self._coerce_probability(item.get("confidence_score"), default=0.65),
                    is_estimated=True,
                )
            )
        if parsed:
            return parsed[:6]
        return self._default_competitor_visibility(competitors)

    def _parse_citation_likelihood(
        self,
        values: list[dict[str, Any]],
        candidate_keywords: list[KeywordOpportunity],
        query_results: list[AISOVQueryResult],
    ) -> list[AISOVCitationLikelihood]:
        parsed: list[AISOVCitationLikelihood] = []
        seen: set[str] = set()
        for item in values:
            keyword = self._clean_text(item.get("keyword")).lower()
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            parsed.append(
                AISOVCitationLikelihood(
                    keyword=keyword,
                    citation_likelihood_score=self._coerce_probability(item.get("citation_likelihood_score"), default=0.35),
                    reason=self._clean_text(item.get("reason")),
                    confidence_score=self._coerce_probability(item.get("confidence_score"), default=0.62),
                )
            )
        if parsed:
            return parsed[:15]

        lookup = {item.keyword.lower(): item for item in candidate_keywords}
        derived: list[AISOVCitationLikelihood] = []
        for result in query_results:
            if result.keyword.lower() in seen:
                continue
            seen.add(result.keyword.lower())
            derived.append(
                AISOVCitationLikelihood(
                    keyword=result.keyword,
                    citation_likelihood_score=result.citation_likelihood_score,
                    reason=result.reason or "Estimated from hybrid AI SOV query-level reasoning.",
                    confidence_score=result.confidence_score or lookup.get(result.keyword.lower(), None).confidence_score if lookup.get(result.keyword.lower()) else 0.6,
                )
            )
        return derived[:15]

    def _default_competitor_visibility(self, competitors: list[CompetitorRecord]) -> list[AISOVCompetitorVisibility]:
        results: list[AISOVCompetitorVisibility] = []
        for item in competitors[:6]:
            score = min(max((item.estimated_strength / 100) * 0.85, 0.2), 0.92)
            summary = (
                f"{item.name or item.domain} is likely to appear in AI answers for overlapping services"
                f"{' in the target market' if item.reason_for_selection else ''}."
            )
            results.append(
                AISOVCompetitorVisibility(
                    domain=item.domain,
                    name=item.name,
                    likely_visibility_score=round(score, 2),
                    summary=summary,
                    confidence_score=max(item.confidence_score, 0.55),
                    is_estimated=True,
                )
            )
        return results

    def _synthesize_engine_results(
        self,
        query_results: list[AISOVQueryResult],
        overall_score: float,
        status: str,
    ) -> list[AISOVEngineResult]:
        adjustments = {
            "google_ai_overviews": -0.03,
            "perplexity": 0.02,
            "chatgpt": 0.0,
        }
        results: list[AISOVEngineResult] = []
        target_queries = len(query_results)
        for engine in self.ENGINES:
            score = max(0.05, min(0.95, round(overall_score + adjustments[engine], 2)))
            cited_queries = min(target_queries, round(score * target_queries))
            results.append(
                AISOVEngineResult(
                    engine=engine,
                    status=status,
                    target_queries=target_queries,
                    cited_queries=cited_queries,
                    score=score,
                    notes=[
                        "Estimated engine-level AI SOV score generated without live provider measurement.",
                    ],
                )
            )
        return results

    def _default_brand_visibility_summary(
        self,
        overall_score: float,
        brand_name: str,
        query_results: list[AISOVQueryResult],
        competitor_visibility: list[AISOVCompetitorVisibility],
    ) -> str:
        cited_count = len([item for item in query_results if item.brand_likely_cited])
        competitor_count = len(competitor_visibility)
        if overall_score >= 0.65:
            posture = "shows relatively strong estimated visibility"
        elif overall_score >= 0.4:
            posture = "shows moderate estimated visibility with uneven coverage"
        else:
            posture = "shows limited estimated AI visibility and clear opportunity gaps"
        return (
            f"{brand_name} {posture} across the sampled AI answer set. "
            f"The brand is estimated to be cited for {cited_count} of {len(query_results)} tracked queries, "
            f"while {competitor_count} competitor domains look more citation-ready for overlapping service demand."
        )

    def _default_recommended_actions(
        self,
        query_results: list[AISOVQueryResult],
        request: Module0Request | None,
        website_profile: WebsiteProfile | None,
    ) -> list[str]:
        location = request.target_locations[0] if request and request.target_locations else "the target market"
        service = request.priority_services[0] if request and request.priority_services else (
            request.services_or_products[0] if request and request.services_or_products else "the primary service"
        )
        gaps = [item for item in query_results if not item.brand_likely_cited][:4]
        actions = [
            f"Create or strengthen a local service page for {service} in {location} with concise answer blocks and service proof.",
            "Add FAQ-style sections that answer cost, timing, and service-selection questions in short citation-friendly paragraphs.",
            "Expand schema and entity consistency signals so AI systems can better connect the brand to the service category.",
        ]
        if website_profile and not website_profile.detected_schema_types:
            actions.append("Add Organization, LocalBusiness, Service, and FAQ schema coverage where appropriate.")
        if gaps:
            actions.append(
                f"Build content specifically for missing visibility queries such as {', '.join(item.query for item in gaps[:2])}."
            )
        return actions[:8]

    def _derive_content_gap(
        self,
        keyword: KeywordOpportunity,
        fan_out_map: FanOutMap | None,
        website_profile: WebsiteProfile | None,
    ) -> str:
        if not keyword.mapped_url:
            return "No clearly mapped landing page supports this query yet."
        if fan_out_map:
            match = next((item for item in fan_out_map.keyword_maps if item.root_keyword == keyword.keyword), None)
            if match and match.invisible_keywords:
                return f"Missing fan-out coverage for subtopics such as {', '.join(match.invisible_keywords[:2])}."
        if website_profile and website_profile.homepage_text_excerpt:
            if keyword.keyword.split()[0] not in (website_profile.homepage_text_excerpt or "").lower():
                return "The current site summary does not strongly reinforce this query or answer intent."
        return "The mapped page likely needs stronger AEO formatting, location proof, or entity reinforcement."

    def _derive_content_action(self, keyword: KeywordOpportunity, request: Module0Request | None) -> str:
        location = request.target_locations[0] if request and request.target_locations else "the target market"
        if keyword.intent == KeywordIntent.INFORMATIONAL:
            return f"Publish an FAQ-style answer module for '{keyword.keyword}' and connect it to a service page for {location}."
        if keyword.intent == KeywordIntent.NAVIGATIONAL_AEO:
            return f"Strengthen brand/service trust signals and concise comparison copy for '{keyword.keyword}'."
        return f"Improve the primary service page targeting '{keyword.keyword}' with pricing, proof, and location-specific answer blocks."

    def _derive_reason(
        self,
        keyword: KeywordOpportunity,
        brand_name: str,
        competitors_likely_cited: list[str],
        entity_factor: float,
        website_profile: WebsiteProfile | None,
    ) -> str:
        support_signals: list[str] = []
        if (keyword.ai_answer_trigger_rate or 0) >= 0.55:
            support_signals.append("the query is likely to trigger AI answers")
        if entity_factor >= 0.5:
            support_signals.append("the brand has moderate entity reinforcement")
        if keyword.intent == KeywordIntent.TRANSACTIONAL:
            support_signals.append("service intent usually favors brands with strong local proof")
        if website_profile and website_profile.detected_schema_types:
            support_signals.append("structured data signals are present on the site")
        if not support_signals:
            support_signals.append("the brand currently lacks strong evidence for consistent AI citation")
        competitor_note = (
            f" Competitors such as {', '.join(competitors_likely_cited[:2])} may be cited first."
            if competitors_likely_cited
            else ""
        )
        return f"For {brand_name}, {', '.join(support_signals)}.{competitor_note}"

    def _estimated_query_score(
        self,
        keyword: KeywordOpportunity,
        entity_factor: float,
        request: Module0Request | None,
        website_profile: WebsiteProfile | None,
    ) -> float:
        local_bonus = 0.08 if request and request.target_locations and any(
            location.lower() in keyword.keyword.lower() for location in request.target_locations
        ) else 0.0
        mapped_bonus = 0.08 if keyword.mapped_url else -0.04
        schema_bonus = 0.05 if website_profile and website_profile.detected_schema_types else 0.0
        base = (
            0.14
            + ((keyword.ai_answer_trigger_rate or 0.0) * 0.35)
            + (keyword.confidence_score * 0.12)
            + (keyword.quality_score * 0.14)
            + (entity_factor * 0.17)
            + local_bonus
            + mapped_bonus
            + schema_bonus
        )
        if keyword.intent == KeywordIntent.INFORMATIONAL:
            base += 0.08
        if keyword.priority.value == "P1":
            base += 0.03
        return max(0.08, min(0.92, round(base, 2)))

    def _normalize_intent(
        self,
        value: Any,
        default: KeywordIntent | None,
    ) -> KeywordIntent:
        normalized = str(value or "").strip()
        try:
            return KeywordIntent(normalized)
        except ValueError:
            return default or KeywordIntent.INFORMATIONAL

    def _extract_content(self, body: dict[str, Any]) -> str:
        choices = body.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            return "\n".join(parts).strip()
        return ""

    def _strip_code_fence(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return stripped

    def _clean_string_list(self, values: Any, limit: int) -> list[str]:
        if not isinstance(values, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = self._clean_text(value)
            lowered = text.lower()
            if not text or lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(text)
            if len(cleaned) >= limit:
                break
        return cleaned

    def _clean_text(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    def _coerce_probability(self, value: Any, default: float) -> float:
        try:
            parsed = float(str(value).strip())
        except (TypeError, ValueError):
            return max(0.0, min(1.0, default))
        return max(0.0, min(1.0, round(parsed, 2)))

    def _to_int(self, value: Any) -> int:
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return 0

    def _average(self, values: list[float]) -> float:
        filtered = [value for value in values if value is not None]
        if not filtered:
            return 0.0
        return round(sum(filtered) / len(filtered), 2)

    def _name_from_domain(self, domain: str) -> str:
        root = domain.split(".")[0]
        tokens = [token for token in re.split(r"[-_]+", root) if token]
        return " ".join(token.capitalize() for token in tokens[:6]) or domain

    def _get_client(self) -> httpx.Client:
        if self.http_client is not None:
            return _SharedClientContext(self.http_client)
        return httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))


class _SharedClientContext:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False
