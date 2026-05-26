from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import dataclass, field
from typing import Any

import httpx

from tr_seo_contracts.module0 import CDDExtraction, Module0Request, SiteClassification, WebsiteProfile
from tr_seo_module0.business_context import BusinessContextAnalyzer


class OpenAIFallbackError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(slots=True)
class OpenAIKeywordEstimate:
    keyword: str
    search_volume: int
    keyword_difficulty: int
    current_position: int | None
    cpc: float | None
    intent: str
    priority: str
    mapped_url: str | None
    ai_answer_trigger_rate: float
    confidence_score: float
    quality_score: float
    notes: list[str]


@dataclass(slots=True)
class OpenAICompetitorEstimate:
    domain: str
    name: str
    reason_for_selection: str
    likely_services: list[str]
    content_gaps: list[str]
    service_gaps: list[str]
    estimated_strength: int
    confidence_score: float
    keyword_sample: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OpenAIKeywordFallbackResult:
    keywords: list[OpenAIKeywordEstimate]
    competitors: list[OpenAICompetitorEstimate]
    notes: list[str]


class OpenAIKeywordFallbackService:
    BASE_URL = "https://api.openai.com/v1/chat/completions"
    MIN_SUPPLEMENT_KEYWORDS = 12
    MIN_RECOVERY_KEYWORDS = 8
    QUALITY_SCORE_THRESHOLD = 0.68
    MEANINGFUL_TOKEN_LIMIT = 6
    STOPWORDS = {
        "the",
        "a",
        "an",
        "and",
        "for",
        "of",
        "in",
        "to",
        "near",
        "me",
        "service",
        "services",
        "company",
        "business",
    }
    NOISE_TOKENS = {
        "observed",
        "urls",
        "url",
        "pages",
        "page",
        "about",
        "contact",
        "gallery",
        "safe",
        "crawl",
        "signals",
        "signal",
        "module",
        "preview",
        "summary",
        "sections",
        "section",
        "detected",
        "public",
        "profile",
        "onboarding",
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.http_client = http_client
        self.context_analyzer = BusinessContextAnalyzer()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        request: Module0Request,
        cdd_extraction: CDDExtraction | None,
        site_classification: SiteClassification | None,
        website_profile: WebsiteProfile | None,
        keyword_limit: int,
        competitor_limit: int,
    ) -> OpenAIKeywordFallbackResult:
        if not self.api_key:
            raise OpenAIFallbackError("missing_api_key", "OPENAI_API_KEY is not configured.")

        keyword_limit = max(1, min(keyword_limit, 200))
        competitor_limit = max(1, min(competitor_limit, 10))
        payload = self._build_payload(
            request,
            cdd_extraction,
            site_classification,
            website_profile,
            keyword_limit,
            competitor_limit,
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
            raise OpenAIFallbackError("timeout", "OpenAI fallback request timed out.") from error
        except httpx.HTTPStatusError as error:
            raise OpenAIFallbackError(
                "api_access_error",
                f"OpenAI fallback returned HTTP {error.response.status_code}.",
            ) from error
        except httpx.HTTPError as error:
            raise OpenAIFallbackError("api_access_error", "OpenAI fallback request failed.") from error

        body = response.json()
        content = self._extract_content(body)
        if not content:
            raise OpenAIFallbackError("empty_response", "OpenAI fallback returned no content.")

        try:
            parsed = json.loads(self._strip_code_fence(content))
        except json.JSONDecodeError as error:
            raise OpenAIFallbackError("invalid_json", "OpenAI fallback returned invalid JSON.") from error

        keywords = self._parse_keywords(
            parsed.get("keywords", []),
            request,
            site_classification,
            website_profile,
            keyword_limit,
        )
        competitors = self._parse_competitors(parsed.get("competitors", []), request, competitor_limit)
        if not keywords:
            raise OpenAIFallbackError("empty_keywords", "OpenAI fallback returned no keyword estimates.")
        if not competitors:
            raise OpenAIFallbackError("empty_competitors", "OpenAI fallback returned no competitors.")

        notes = [str(item).strip() for item in parsed.get("notes", []) if str(item).strip()]
        return OpenAIKeywordFallbackResult(
            keywords=keywords,
            competitors=competitors,
            notes=notes[:12],
        )

    def _build_payload(
        self,
        request: Module0Request,
        cdd_extraction: CDDExtraction | None,
        site_classification: SiteClassification | None,
        website_profile: WebsiteProfile | None,
        keyword_limit: int,
        competitor_limit: int,
    ) -> dict[str, Any]:
        competitor_hints = cdd_extraction.competitor_hints if cdd_extraction else []
        detected_domains = cdd_extraction.detected_domains if cdd_extraction else []
        cdd_preview = cdd_extraction.text_preview if cdd_extraction else ""
        url_inventory = website_profile.url_inventory if website_profile else None

        system_prompt = (
            "You are generating estimated SEO fallback intelligence when SEMrush credits are unavailable. "
            "Return only valid JSON. Produce fewer, stronger outputs instead of noisy bulk output. "
            "Avoid fake garbage like concatenated brand strings, 'brand au company', 'keyword 174', or "
            "placeholder competitors. Favor realistic Australian local SEO terms for the business context. "
            "All values are estimated, not real provider metrics. Use domain, services, locations, CDD, and "
            "competitor hints to produce commercially credible output."
        )

        user_payload = {
            "task": "Generate strong estimated Module 0 fallback keyword and competitor intelligence.",
            "requirements": {
                "max_keywords": keyword_limit,
                "max_competitors": competitor_limit,
                "target_country": request.target_country,
                "brand_name": request.brand_name,
                "business_type": getattr(request.business_type, "value", str(request.business_type)),
                "website_url": str(request.website_url),
                "domain": request.domain,
                "services_or_products": request.services_or_products,
                "target_locations": request.target_locations,
                "business_goals": request.business_goals,
                "priority_services": request.priority_services,
                "known_competitors": request.known_competitors,
                "business_type_from_site": site_classification.business_type.value if site_classification else None,
                "cms": site_classification.cms if site_classification else None,
                "site_scale_tier": site_classification.site_scale_tier if site_classification else None,
                "cdd_competitor_hints": competitor_hints,
                "cdd_detected_domains": detected_domains,
                "cdd_preview": cdd_preview[:2500],
                "homepage_title": website_profile.homepage_title if website_profile else None,
                "meta_description": website_profile.meta_description if website_profile else None,
                "homepage_text_excerpt": website_profile.homepage_text_excerpt if website_profile else None,
                "sample_page_titles": website_profile.sample_page_titles if website_profile else [],
                "sample_urls": url_inventory.sample_urls[:12] if url_inventory else [],
                "service_like_urls": url_inventory.service_like_urls[:12] if url_inventory else [],
                "location_like_urls": url_inventory.location_like_urls[:12] if url_inventory else [],
                "site_sections": [section.section for section in (url_inventory.top_sections if url_inventory else [])[:8]],
                "keyword_mix": [
                    "core_service",
                    "local_area",
                    "commercial_research",
                    "urgent_problem",
                    "material_product",
                    "informational_aeo",
                ],
                "keyword_quality_rules": [
                    "Generate no more than the requested maximum number of high-quality keywords.",
                    "Do not force the output to hit the limit. It is acceptable to return fewer keywords when the stronger set is smaller.",
                    "Generate realistic Google search queries for a local service business.",
                    "Generate 5-10 strong keywords per category when possible, but never force quantity.",
                    "Most keywords should be 2-6 meaningful words. Longer keywords are acceptable only when they are natural question queries.",
                    "No repetition or near-duplicates.",
                    "Do not generate keyword soup, stacked modifiers, or sentence fragments.",
                    "Do not combine quote, pricing, reviews, best, cheap, affordable, company, specialist, and near me unnaturally.",
                    "No low-quality filler like brandname au company, keyword 174, or generic brand-only phrases.",
                    "Do not return scraped page-title fragments, sentence fragments, or long heading text.",
                    "Prefer fewer strong commercial keywords over many weak ones.",
                    "Use one clear intent per keyword.",
                    "Base keywords on business type, services/products, target locations, sitemap URLs, page titles, and website content.",
                    "Every keyword must include search_volume, keyword_difficulty, cpc, intent, priority, mapped_url, ai_answer_trigger_rate, confidence_score, and quality_score.",
                ],
                "competitor_quality_rules": [
                    "Use real or realistic competitors relevant to the niche and location.",
                    "Prefer competitors explicitly mentioned in the CDD or user-provided project inputs.",
                    "Never use placeholder domains like competitor-1.com.",
                    "Every competitor must include domain, name, reason_for_selection, likely_services, content_gaps, service_gaps, estimated_strength, and confidence_score.",
                ],
            },
            "output_schema": {
                "keywords": [
                    {
                        "category": "core_service | local_area | commercial_research | urgent_problem | material_product | informational_aeo",
                        "keyword": "string",
                        "search_volume": "integer estimated monthly searches",
                        "keyword_difficulty": "integer 0-100 estimated difficulty",
                        "current_position": "integer 1-30 or null estimated ranking",
                        "cpc": "number estimated CPC or null",
                        "intent": "transactional | navigational_aeo | informational",
                        "priority": "P1 | P2 | P3",
                        "mapped_url": "suggested relative URL string",
                        "ai_answer_trigger_rate": "number 0-1",
                        "confidence_score": "number 0-1",
                        "quality_score": "number 0-1",
                        "notes": ["short reasoning notes"],
                    }
                ],
                "competitors": [
                    {
                        "domain": "domain string",
                        "name": "business name",
                        "reason_for_selection": "why it competes",
                        "likely_services": ["service strings"],
                        "content_gaps": ["content gaps"],
                        "service_gaps": ["service gaps"],
                        "estimated_strength": "integer 0-100",
                        "confidence_score": "number 0-1",
                        "keyword_sample": ["keyword sample strings"],
                        "notes": ["short notes"],
                    }
                ],
                "notes": ["top-level notes about assumptions"],
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

    def _parse_keywords(
        self,
        raw_keywords: list[dict[str, Any]],
        request: Module0Request,
        site_classification: SiteClassification | None,
        website_profile: WebsiteProfile | None,
        keyword_limit: int,
    ) -> list[OpenAIKeywordEstimate]:
        parsed: list[OpenAIKeywordEstimate] = []
        seen_signatures: set[str] = set()
        brand_lower = request.brand_name.strip().lower()
        compact_brand = re.sub(r"[^a-z0-9]+", "", brand_lower)
        banned_domain_tokens = self._domain_tokens(request)
        context = self.context_analyzer.build(
            request=request,
            site_classification=site_classification,
            website_profile=website_profile,
        )

        for item in raw_keywords:
            keyword = self._clean_keyword(item.get("keyword"))
            if not keyword:
                continue
            if not self._is_high_quality_keyword(
                keyword,
                brand_lower,
                compact_brand,
                banned_domain_tokens,
                context,
            ):
                continue
            signature = self._keyword_signature(keyword)
            if signature in seen_signatures:
                continue
            if self._is_near_duplicate(keyword, parsed):
                continue
            seen_signatures.add(signature)
            intent = self._normalize_enum_value(
                item.get("intent"),
                {"transactional", "navigational_aeo", "informational"},
                "informational",
            )
            priority = self._normalize_enum_value(
                item.get("priority"),
                {"P1", "P2", "P3"},
                "P2",
            )
            quality_score = self._to_probability(item.get("quality_score"), default=0.78)
            if quality_score < self.QUALITY_SCORE_THRESHOLD:
                continue
            parsed.append(
                OpenAIKeywordEstimate(
                    keyword=keyword,
                    search_volume=self._estimate_search_volume(item.get("search_volume"), keyword, intent),
                    keyword_difficulty=self._estimate_keyword_difficulty(item.get("keyword_difficulty"), keyword),
                    current_position=self._estimate_position(
                        item.get("current_position"),
                        keyword,
                        intent,
                        priority,
                    ),
                    cpc=self._estimate_cpc(item.get("cpc"), keyword, intent),
                    intent=intent,
                    priority=priority,
                    mapped_url=self._clean_mapped_url(item.get("mapped_url"))
                    or self._default_mapped_url(keyword, intent, context),
                    ai_answer_trigger_rate=self._estimate_ai_trigger_rate(
                        item.get("ai_answer_trigger_rate"),
                        keyword,
                        intent,
                    ),
                    confidence_score=self._to_probability(item.get("confidence_score"), default=0.72),
                    quality_score=quality_score,
                    notes=[
                        str(note).strip()
                        for note in item.get("notes", [])
                        if str(note).strip()
                    ][:5],
                )
            )
            if len(parsed) >= keyword_limit:
                break
        if len(parsed) < min(self.MIN_SUPPLEMENT_KEYWORDS, keyword_limit):
            parsed = self._supplement_keywords_from_evidence(
                parsed,
                request,
                site_classification,
                website_profile,
                keyword_limit,
                context,
            )
        if len(parsed) < min(self.MIN_RECOVERY_KEYWORDS, keyword_limit):
            parsed = self._recover_keywords_from_context(
                parsed,
                request,
                site_classification,
                website_profile,
                keyword_limit,
                context,
            )
        parsed.sort(
            key=lambda item: (
                {"P1": 0, "P2": 1, "P3": 2}.get(item.priority, 3),
                -item.quality_score,
                -item.confidence_score,
                -item.search_volume,
                item.keyword,
            )
        )
        return parsed

    def _parse_competitors(
        self,
        raw_competitors: list[dict[str, Any]],
        request: Module0Request,
        competitor_limit: int,
    ) -> list[OpenAICompetitorEstimate]:
        parsed: list[OpenAICompetitorEstimate] = []
        seen_domains: set[str] = set()
        own_domain = self._normalize_domain(request.domain or str(request.website_url))

        for item in raw_competitors:
            domain = self._normalize_domain(item.get("domain", ""))
            if not domain or domain == own_domain or domain in seen_domains:
                continue
            if not self._is_plausible_competitor_domain(domain):
                continue
            seen_domains.add(domain)
            parsed.append(
                OpenAICompetitorEstimate(
                    domain=domain,
                    name=self._clean_title(item.get("name")) or self._title_from_domain(domain),
                    reason_for_selection=(
                        str(item.get("reason_for_selection", "")).strip()
                        or "Estimated competitor selected from the niche, location, and project context."
                    ),
                    likely_services=self._clean_string_list(item.get("likely_services", []), 8),
                    content_gaps=self._clean_string_list(item.get("content_gaps", []), 8),
                    service_gaps=self._clean_string_list(item.get("service_gaps", []), 8),
                    estimated_strength=self._estimate_strength(item.get("estimated_strength"), domain),
                    confidence_score=self._to_probability(item.get("confidence_score"), default=0.68),
                    keyword_sample=self._clean_keyword_list(item.get("keyword_sample", []), 8),
                    notes=self._clean_string_list(item.get("notes", []), 5),
                )
            )
            if len(parsed) >= competitor_limit:
                break
        parsed.sort(key=lambda item: (-item.confidence_score, -item.estimated_strength, item.domain))
        return parsed

    def _clean_keyword(self, value: Any) -> str:
        keyword = re.sub(r"\s+", " ", str(value or "").strip().lower())
        token_map = {
            "replacements": "replacement",
            "installations": "installation",
            "prices": "price",
            "quotes": "quote",
        }
        tokens = [token_map.get(token, token) for token in keyword.split()]
        keyword = " ".join(tokens)
        return keyword

    def _is_high_quality_keyword(
        self,
        keyword: str,
        brand_lower: str,
        compact_brand: str,
        banned_domain_tokens: set[str],
        context,
    ) -> bool:
        if len(keyword) < 3:
            return False
        lowered = keyword.lower()
        tokens = [token for token in re.split(r"\W+", lowered) if token]
        if len(tokens) < 2:
            return False
        meaningful_tokens = [token for token in tokens if token not in self.STOPWORDS]
        if len(meaningful_tokens) > self.MEANINGFUL_TOKEN_LIMIT and not self._is_natural_question_keyword(lowered):
            return False
        if re.search(r"\bkeyword\s*\d+\b", lowered):
            return False
        if re.search(r"\b\d+\b$", lowered):
            return False
        if "reviews reviews" in lowered or "pricing pricing" in lowered:
            return False
        if len(set(tokens)) <= 1:
            return False
        if self._has_repeated_term_pattern(tokens):
            return False
        if self._has_stacked_modifiers(tokens):
            return False
        if self._looks_like_scraped_fragment(lowered, tokens):
            return False
        if compact_brand and compact_brand in lowered.replace(" ", "") and brand_lower not in lowered:
            return False
        if any(token in banned_domain_tokens for token in tokens):
            return False
        if self._contains_noise_tokens(tokens):
            return False
        if any(tld in tokens for tld in {"com", "au", "net", "org"}):
            return False
        banned_phrases = {
            " au company",
            " au service",
            " au specialist",
            " brand name",
            " official site",
        }
        if any(token in lowered for token in banned_phrases):
            return False
        if lowered == brand_lower:
            return False
        if not self.context_analyzer.is_valid_query(keyword, context):
            return False
        return True

    def _keyword_signature(self, keyword: str) -> str:
        tokens = [token for token in re.split(r"\W+", keyword.lower()) if token and token not in self.STOPWORDS]
        if not tokens:
            tokens = keyword.lower().split()
        return " ".join(sorted(dict.fromkeys(tokens))[:6])

    def _clean_mapped_url(self, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        if not cleaned:
            return None
        if not cleaned.startswith("/"):
            cleaned = f"/{cleaned.lstrip('/')}"
        cleaned = re.sub(r"//+", "/", cleaned)
        return cleaned

    def _clean_title(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    def _clean_string_list(self, values: Any, limit: int) -> list[str]:
        if not isinstance(values, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = self._clean_title(value)
            lowered = text.lower()
            if not text or lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(text)
            if len(cleaned) >= limit:
                break
        return cleaned

    def _clean_keyword_list(self, values: Any, limit: int) -> list[str]:
        if not isinstance(values, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            keyword = self._clean_keyword(value)
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            cleaned.append(keyword)
            if len(cleaned) >= limit:
                break
        return cleaned

    def _domain_tokens(self, request: Module0Request) -> set[str]:
        domain = self._normalize_domain(request.domain or str(request.website_url))
        hostname = domain.split(".")[0]
        tokens = {token for token in re.split(r"[-_.]+", hostname) if len(token) > 2}
        return tokens

    def _is_near_duplicate(
        self,
        keyword: str,
        existing: list[OpenAIKeywordEstimate],
    ) -> bool:
        candidate_tokens = self._keyword_token_set(keyword)
        if not candidate_tokens:
            return False
        for item in existing:
            existing_tokens = self._keyword_token_set(item.keyword)
            if not existing_tokens:
                continue
            overlap = len(candidate_tokens & existing_tokens) / max(len(candidate_tokens | existing_tokens), 1)
            if overlap >= 0.82:
                return True
            if candidate_tokens.issubset(existing_tokens) or existing_tokens.issubset(candidate_tokens):
                if len(candidate_tokens ^ existing_tokens) <= 1:
                    return True
        return False

    def _keyword_token_set(self, keyword: str) -> set[str]:
        return {
            token
            for token in re.split(r"\W+", keyword.lower())
            if token and token not in self.STOPWORDS and not token.isdigit()
        }

    def _supplement_keywords_from_evidence(
        self,
        parsed: list[OpenAIKeywordEstimate],
        request: Module0Request,
        site_classification: SiteClassification | None,
        website_profile: WebsiteProfile | None,
        keyword_limit: int,
        context,
    ) -> list[OpenAIKeywordEstimate]:
        brand_lower = request.brand_name.strip().lower()
        compact_brand = re.sub(r"[^a-z0-9]+", "", brand_lower)
        banned_domain_tokens = self._domain_tokens(request)
        seen_signatures = {self._keyword_signature(item.keyword) for item in parsed}
        candidate_phrases = self._context_service_phrases(context) or self._evidence_phrases(request, website_profile)
        locations = [self._clean_keyword(location) for location in request.target_locations if location.strip()]
        locations = [location for location in locations if location]
        templates = [
            "{service} {location}",
            "{service} cost",
            "{service} cost {location}",
            "commercial {service} {location}",
            "emergency {service}",
            "how much does {service} cost",
            "how much does {service} cost in {location}",
        ]

        for service in candidate_phrases:
            for location in locations or ["melbourne"]:
                for template in templates:
                    keyword = template.format(service=service, location=location).strip().lower()
                    keyword = re.sub(r"\s+", " ", keyword)
                    if not self._is_high_quality_keyword(keyword, brand_lower, compact_brand, banned_domain_tokens, context):
                        continue
                    signature = self._keyword_signature(keyword)
                    if signature in seen_signatures:
                        continue
                    if self._is_near_duplicate(keyword, parsed):
                        continue
                    seen_signatures.add(signature)
                    intent = self._infer_intent(keyword)
                    priority = self._infer_priority(keyword)
                    parsed.append(
                        OpenAIKeywordEstimate(
                            keyword=keyword,
                            search_volume=self._estimate_search_volume(None, keyword, intent),
                            keyword_difficulty=self._estimate_keyword_difficulty(None, keyword),
                            current_position=self._estimate_position(None, keyword, intent, priority),
                            cpc=self._estimate_cpc(None, keyword, intent),
                            intent=intent,
                            priority=priority,
                            mapped_url=self._default_mapped_url(keyword, intent, context),
                            ai_answer_trigger_rate=self._estimate_ai_trigger_rate(None, keyword, intent),
                            confidence_score=0.66,
                            quality_score=0.72,
                            notes=["Supplemented from site evidence after OpenAI fallback filtering."],
                        )
                    )
                    if len(parsed) >= keyword_limit:
                        return parsed
        return parsed

    def _evidence_phrases(
        self,
        request: Module0Request,
        website_profile: WebsiteProfile | None,
    ) -> list[str]:
        phrases: list[str] = []
        seen: set[str] = set()

        def add_phrase(value: str) -> None:
            cleaned = self._normalize_phrase(value)
            if not cleaned or cleaned in seen:
                return
            seen.add(cleaned)
            phrases.append(cleaned)

        for service in request.services_or_products + request.priority_services:
            add_phrase(service)
        for phrase in self._brand_service_phrases(request):
            add_phrase(phrase)

        if website_profile:
            add_phrase(website_profile.homepage_title or "")
            add_phrase(website_profile.meta_description or "")
            for title in website_profile.sample_page_titles:
                for phrase in self._phrases_from_text(title):
                    add_phrase(phrase)
            for url in website_profile.url_inventory.service_like_urls[:12]:
                for phrase in self._phrases_from_url(url):
                    add_phrase(phrase)
            for url in website_profile.url_inventory.location_like_urls[:8]:
                for phrase in self._phrases_from_url(url):
                    add_phrase(phrase)
            for phrase in self._phrases_from_text(website_profile.homepage_text_excerpt or ""):
                add_phrase(phrase)

        return phrases[:10]

    def _recover_keywords_from_context(
        self,
        parsed: list[OpenAIKeywordEstimate],
        request: Module0Request,
        site_classification: SiteClassification | None,
        website_profile: WebsiteProfile | None,
        keyword_limit: int,
        context,
    ) -> list[OpenAIKeywordEstimate]:
        brand_lower = request.brand_name.strip().lower()
        compact_brand = re.sub(r"[^a-z0-9]+", "", brand_lower)
        banned_domain_tokens = self._domain_tokens(request)
        seen_signatures = {self._keyword_signature(item.keyword) for item in parsed}
        phrases = self._context_service_phrases(context) or self._evidence_phrases(request, website_profile)
        locations = self._location_candidates(request, website_profile)
        templates = [
            "{service}",
            "{service} {location}",
            "{service} cost",
            "{service} cost {location}",
            "commercial {service} {location}",
            "emergency {service}",
            "how much does {service} cost",
        ]
        if site_classification and site_classification.business_type.value == "service":
            templates.extend(
                [
                    "{service} installation",
                    "{service} repair",
                    "{service} replacement",
                    "{service} installation {location}",
                    "{service} repair {location}",
                    "{service} replacement {location}",
                ]
            )

        for service in phrases:
            for template in templates:
                for location in locations:
                    if "{location}" in template and not location:
                        continue
                    keyword = template.format(service=service, location=location).strip().lower()
                    keyword = re.sub(r"\s+", " ", keyword)
                    if not self._is_high_quality_keyword(keyword, brand_lower, compact_brand, banned_domain_tokens, context):
                        continue
                    signature = self._keyword_signature(keyword)
                    if signature in seen_signatures:
                        continue
                    if self._is_near_duplicate(keyword, parsed):
                        continue
                    seen_signatures.add(signature)
                    intent = self._infer_intent(keyword)
                    priority = self._infer_priority(keyword)
                    parsed.append(
                        OpenAIKeywordEstimate(
                            keyword=keyword,
                            search_volume=self._estimate_search_volume(None, keyword, intent),
                            keyword_difficulty=self._estimate_keyword_difficulty(None, keyword),
                            current_position=self._estimate_position(None, keyword, intent, priority),
                            cpc=self._estimate_cpc(None, keyword, intent),
                            intent=intent,
                            priority=priority,
                            mapped_url=self._default_mapped_url(keyword, intent, context),
                            ai_answer_trigger_rate=self._estimate_ai_trigger_rate(None, keyword, intent),
                            confidence_score=0.62,
                            quality_score=0.7,
                            notes=["Recovered from site and project context after aggressive keyword filtering."],
                        )
                    )
                    if len(parsed) >= keyword_limit:
                        return parsed
        return parsed

    def _phrases_from_text(self, text: str) -> list[str]:
        if not text:
            return []
        cleaned = re.sub(r"[^a-z0-9\s/-]", " ", text.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        phrases: list[str] = []
        for chunk in re.split(r"[|,/:\-]", cleaned):
            normalized = self._normalize_phrase(chunk)
            if normalized:
                phrases.append(normalized)
        return phrases[:12]

    def _phrases_from_url(self, url: str) -> list[str]:
        path_parts = [part for part in url.split("/")[3:] if part]
        if not path_parts:
            return []
        candidates: list[str] = []
        for size in (1, 2):
            segment_group = path_parts[-size:]
            raw = " ".join(
                segment.replace("-", " ").replace("_", " ")
                for segment in segment_group
                if segment not in self.NOISE_TOKENS
            ).strip()
            normalized = self._normalize_phrase(raw)
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates[:3]

    def _normalize_phrase(self, value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())
        cleaned = re.sub(
            r"\b(home|page|pages|blog|blogs|category|categories|services|service|location|locations|our|your)\b",
            " ",
            cleaned,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        tokens = [token for token in cleaned.split() if len(token) > 2 and token not in {"www", "http", "https"}]
        token_map = {
            "replacements": "replacement",
            "installations": "installation",
            "prices": "price",
            "quotes": "quote",
        }
        tokens = [token_map.get(token, token) for token in tokens]
        if len(tokens) < 2:
            return ""
        if len(tokens) > 6:
            return ""
        if self._contains_noise_tokens(tokens):
            return ""
        meaningful = [token for token in tokens if token not in self.STOPWORDS]
        if len(set(meaningful)) <= 1:
            return ""
        if self._has_repeated_term_pattern(tokens):
            return ""
        if self._looks_like_scraped_fragment(" ".join(tokens), tokens):
            return ""
        return " ".join(tokens[:5])

    def _brand_service_phrases(self, request: Module0Request) -> list[str]:
        phrases: list[str] = []
        seen: set[str] = set()
        location_tokens = {
            token
            for value in request.target_locations
            for token in re.split(r"\W+", value.lower())
            if token and len(token) > 2
        }
        legal_tokens = {"pty", "ltd", "llc", "inc", "group", "co"}

        for raw in [request.brand_name, request.domain or "", str(request.website_url)]:
            cleaned = re.sub(r"https?://", " ", raw.lower())
            cleaned = re.sub(r"[^a-z0-9\\s]", " ", cleaned)
            tokens = [
                token
                for token in cleaned.split()
                if len(token) > 2 and token not in legal_tokens and token not in location_tokens
            ]
            normalized = self._normalize_phrase(" ".join(tokens))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            phrases.append(normalized)
        return phrases[:4]

    def _location_candidates(
        self,
        request: Module0Request,
        website_profile: WebsiteProfile | None,
    ) -> list[str]:
        locations: list[str] = []
        seen: set[str] = set()

        def add_location(value: str) -> None:
            cleaned = self._clean_keyword(value)
            if not cleaned or cleaned in seen:
                return
            if len(cleaned.split()) > 3:
                return
            seen.add(cleaned)
            locations.append(cleaned)

        for location in request.target_locations:
            add_location(location)
        if website_profile:
            for url in website_profile.url_inventory.location_like_urls[:6]:
                for phrase in self._phrases_from_url(url):
                    add_location(phrase)
        if not locations:
            add_location("melbourne")
        return locations[:6]

    def _context_service_phrases(self, context) -> list[str]:
        phrases: list[str] = []
        seen: set[str] = set()
        keep_product_terms = getattr(context.business_type, "value", str(context.business_type)) in {"ecommerce", "hybrid"}
        for phrase in context.service_phrases[:18]:
            root = self.context_analyzer.root_phrase(
                phrase,
                context,
                keep_product_terms=keep_product_terms,
            ) or phrase
            cleaned = self._clean_keyword(root)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            phrases.append(cleaned)
        return phrases[:12]

    def _infer_intent(self, keyword: str) -> str:
        lowered = keyword.lower()
        if any(token in lowered for token in {"how ", "what ", "why ", "cost", "price"}):
            return "informational"
        if any(token in lowered for token in {"near me", "review", "reviews"}):
            return "navigational_aeo"
        return "transactional"

    def _infer_priority(self, keyword: str) -> str:
        lowered = keyword.lower()
        if any(token in lowered for token in {"quote", "cost", "commercial", "emergency"}):
            return "P1"
        if any(token in lowered for token in {"what", "how", "price"}):
            return "P2"
        return "P2"

    def _is_natural_question_keyword(self, keyword: str) -> bool:
        return keyword.startswith(("how ", "what ", "why ", "who ", "where ", "when ", "is ", "do ", "does ", "can ", "should "))

    def _has_repeated_term_pattern(self, tokens: list[str]) -> bool:
        meaningful = [token for token in tokens if token not in self.STOPWORDS and len(token) > 2]
        if len(set(meaningful)) <= 1:
            return True
        repeated = {token for token in meaningful if meaningful.count(token) > 1}
        return bool(repeated)

    def _has_stacked_modifiers(self, tokens: list[str]) -> bool:
        modifier_tokens = [token for token in tokens if token not in self.STOPWORDS]
        commercial_stack = {"quote", "pricing", "price", "prices", "reviews", "review", "estimate", "estimates"}
        authority_stack = {"best", "cheap", "affordable", "company", "specialist", "specialists"}
        near_me_stack = {"near", "me"}

        if sum(1 for token in modifier_tokens if token in commercial_stack) >= 2:
            return True
        if any(token in modifier_tokens for token in near_me_stack) and any(
            token in modifier_tokens for token in authority_stack
        ):
            return True
        if {"quote", "pricing"} & set(modifier_tokens):
            if {"reviews", "review"} & set(modifier_tokens):
                return True
        return False

    def _contains_noise_tokens(self, tokens: list[str]) -> bool:
        meaningful = [token for token in tokens if token not in self.STOPWORDS]
        if not meaningful:
            return True
        noise_hits = [token for token in meaningful if token in self.NOISE_TOKENS]
        if len(noise_hits) >= 1 and len(meaningful) <= 3:
            return True
        if len(noise_hits) >= 2:
            return True
        return False

    def _looks_like_scraped_fragment(self, keyword: str, tokens: list[str]) -> bool:
        sentence_tokens = {
            "essential",
            "role",
            "protecting",
            "homes",
            "benefits",
            "guide",
            "complete",
            "ultimate",
            "small",
        }
        if len(tokens) > 6 and not self._is_natural_question_keyword(keyword):
            return True
        if sum(1 for token in tokens if token in sentence_tokens) >= 2:
            return True
        return False

    def _is_plausible_competitor_domain(self, domain: str) -> bool:
        if "." not in domain:
            return False
        if "competitor-" in domain:
            return False
        if any(token in domain for token in {"example.", "localhost", ".local"}):
            return False
        return bool(re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.[a-z]{2,}", domain))

    def _title_from_domain(self, domain: str) -> str:
        root = domain.split(".")[0]
        tokens = [token for token in re.split(r"[-_]+", root) if token]
        return " ".join(token.capitalize() for token in tokens[:6]) or domain

    def _normalize_domain(self, value: str) -> str:
        cleaned = str(value or "").strip().lower()
        cleaned = re.sub(r"^https?://", "", cleaned)
        cleaned = cleaned.split("/")[0]
        if cleaned.startswith("www."):
            cleaned = cleaned[4:]
        return cleaned

    def _normalize_enum_value(self, value: Any, valid: set[str], default: str) -> str:
        cleaned = str(value or "").strip()
        if cleaned in valid:
            return cleaned
        return default

    def _strip_code_fence(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return stripped

    def _to_int(self, value: Any) -> int:
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return 0

    def _to_optional_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return round(float(str(value).strip()), 2)
        except (TypeError, ValueError):
            return None

    def _to_optional_position(self, value: Any) -> int | None:
        position = self._to_int(value)
        if position <= 0:
            return None
        return min(position, 100)

    def _to_probability(self, value: Any, default: float) -> float:
        try:
            parsed = float(str(value).strip())
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, parsed))

    def _estimate_search_volume(self, value: Any, keyword: str, intent: str) -> int:
        parsed = self._to_int(value)
        if parsed > 0:
            return parsed
        base = 35 + (self._stable_int(keyword, "sv") % 420)
        if intent == "transactional":
            base += 110
        if intent == "navigational_aeo":
            base += 70
        return min(base, 1200)

    def _estimate_keyword_difficulty(self, value: Any, keyword: str) -> int:
        parsed = self._to_int(value)
        if parsed > 0:
            return min(parsed, 100)
        return 18 + (self._stable_int(keyword, "kd") % 55)

    def _estimate_position(self, value: Any, keyword: str, intent: str, priority: str) -> int | None:
        parsed = self._to_optional_position(value)
        if parsed is not None:
            return parsed
        base = 8 + (self._stable_int(keyword, "pos") % 28)
        if priority == "P1":
            base -= 3
        if intent == "transactional":
            base -= 2
        return max(3, min(45, base))

    def _estimate_cpc(self, value: Any, keyword: str, intent: str) -> float:
        parsed = self._to_optional_float(value)
        if parsed is not None and parsed > 0:
            return parsed
        base = 1.25 + ((self._stable_int(keyword, "cpc") % 900) / 100)
        if intent == "transactional":
            base += 2.2
        return round(min(base, 18.0), 2)

    def _estimate_ai_trigger_rate(self, value: Any, keyword: str, intent: str) -> float:
        parsed = self._to_probability(value, default=-1.0)
        if parsed >= 0:
            return parsed
        base = 0.18 + ((self._stable_int(keyword, "ai") % 45) / 100)
        if "how " in keyword or keyword.endswith("?") or intent == "navigational_aeo":
            base += 0.2
        return max(0.05, min(0.95, round(base, 2)))

    def _estimate_strength(self, value: Any, domain: str) -> int:
        parsed = self._to_int(value)
        if parsed > 0:
            return min(parsed, 100)
        return 45 + (self._stable_int(domain, "strength") % 40)

    def _default_mapped_url(self, keyword: str, intent: str, context) -> str:
        root_phrase = self.context_analyzer.root_phrase(
            keyword,
            context,
            keep_product_terms=getattr(context.business_type, "value", str(context.business_type)) in {"ecommerce", "hybrid"},
        )
        tokens = [
            token
            for token in re.split(r"\W+", (root_phrase or keyword).lower())
            if token and token not in self.STOPWORDS
        ]
        slug = "-".join(tokens[:6]) or "estimated-keyword"
        prefix = "/resources" if intent == "informational" or keyword.endswith("?") or keyword.startswith("how ") else "/services"
        return f"{prefix}/{slug}"

    def _stable_int(self, value: str, salt: str) -> int:
        digest = hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

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
