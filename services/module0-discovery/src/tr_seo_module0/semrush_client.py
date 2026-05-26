from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from tr_seo_contracts.module0 import (
    CDDFileMeta,
    CDDExtraction,
    Module0Request,
    SEMrushSnapshot,
    SiteClassification,
    WebsiteProfile,
)
from tr_seo_module0.manual_keyword_upload import ManualKeywordUploadProcessor
from tr_seo_module0.openai_keyword_fallback import (
    OpenAIFallbackError,
    OpenAIKeywordFallbackService,
)

FALLBACK_WARNING = (
    "SEMrush data unavailable due to credits/API access issue. Estimated fallback data was used "
    "for this run."
)


@dataclass(slots=True)
class SEMrushKeywordRecord:
    keyword: str
    search_volume: int
    keyword_difficulty: int
    current_position: int | None
    source: str
    cpc: float | None = None
    intent: str | None = None
    priority: str | None = None
    mapped_url: str | None = None
    ai_answer_trigger_rate: float | None = None
    confidence_score: float = 0.0
    quality_score: float = 0.0
    is_estimated: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SEMrushCompetitorRecord:
    domain: str
    competition_level: float | None
    shared_keywords: int | None
    keyword_sample: list[str]
    name: str = ""
    reason_for_selection: str = ""
    likely_services: list[str] = field(default_factory=list)
    content_gaps: list[str] = field(default_factory=list)
    service_gaps: list[str] = field(default_factory=list)
    estimated_strength: int = 0
    confidence_score: float = 0.0
    is_estimated: bool = False
    source: str = "semrush"
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SEMrushCollectionResult:
    snapshot: SEMrushSnapshot
    keywords: list[SEMrushKeywordRecord]
    competitors: list[SEMrushCompetitorRecord]


class SEMrushAPIError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class SEMrushClient:
    BASE_URL = "https://api.semrush.com/"

    def __init__(
        self,
        api_key: str | None = None,
        region_database: str | None = None,
        test_keyword_limit: int | None = None,
        http_client: httpx.Client | None = None,
        environment: str | None = None,
        openai_fallback_service: OpenAIKeywordFallbackService | None = None,
        manual_keyword_upload_processor: ManualKeywordUploadProcessor | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("SEMRUSH_API_KEY")
        self.region_database = region_database
        self.environment = (environment or os.getenv("ENVIRONMENT", "development")).lower()
        self.force_mock_semrush = self._parse_bool(os.getenv("MODULE0_FORCE_MOCK_SEMRUSH"), default=False)
        self.test_keyword_limit = test_keyword_limit or self._parse_positive_int(
            os.getenv("MODULE0_TEST_KEYWORD_LIMIT"),
            default=200,
        )
        self.production_keyword_limit = self._parse_positive_int(
            os.getenv("MODULE0_PRODUCTION_KEYWORD_LIMIT"),
            default=1000,
        )
        self.competitor_limit = self._parse_positive_int(
            os.getenv("MODULE0_COMPETITOR_LIMIT"),
            default=5,
        )
        self.competitor_keyword_limit = self._parse_positive_int(
            os.getenv("MODULE0_COMPETITOR_KEYWORD_LIMIT"),
            default=15,
        )
        self.http_client = http_client
        self.openai_fallback_service = openai_fallback_service or OpenAIKeywordFallbackService()
        self.manual_keyword_upload_processor = manual_keyword_upload_processor or ManualKeywordUploadProcessor()

    def collect(
        self,
        request: Module0Request,
        cdd_extraction: CDDExtraction | None = None,
        site_classification: SiteClassification | None = None,
        website_profile: WebsiteProfile | None = None,
        manual_keyword_file_meta: CDDFileMeta | None = None,
        manual_keyword_content: bytes | None = None,
    ) -> SEMrushCollectionResult:
        domain = self._normalize_domain(request)
        database = (self.region_database or request.target_country or "us").lower()
        keyword_limit = self._resolve_keyword_limit()
        fallback_keyword_limit = min(keyword_limit, 200)

        if not self.force_mock_semrush and self.api_key:
            try:
                with self._get_client() as client:
                    estimated_traffic = self._fetch_domain_overview(client, domain, database)
                    keywords = self._fetch_domain_keywords(client, domain, database, keyword_limit)
                    competitors = self._fetch_competitors(client, domain, database)

                if not keywords:
                    raise SEMrushAPIError("empty_response", "SEMrush returned no keyword rows.")

                snapshot = SEMrushSnapshot(
                    configured=True,
                    region_database=database,
                    status="live",
                    data_source="semrush",
                    fallback_used=False,
                    is_estimated=False,
                    warning_message=None,
                    keyword_limit=keyword_limit,
                    notes=[
                        "Real SEMrush data was used for this run.",
                        f"Keyword universe limited to {keyword_limit} rows for the current environment.",
                    ],
                    estimated_monthly_traffic=estimated_traffic,
                    estimated_monthly_traffic_history=[estimated_traffic] if estimated_traffic is not None else [],
                    organic_keyword_count=len(keywords),
                    competitors_evaluated=len(competitors),
                )
                return SEMrushCollectionResult(
                    snapshot=snapshot,
                    keywords=keywords[:keyword_limit],
                    competitors=competitors,
                )
            except SEMrushAPIError as error:
                if manual_keyword_file_meta is None or manual_keyword_content is None:
                    return self._fallback_result(
                        request=request,
                        cdd_extraction=cdd_extraction,
                        site_classification=site_classification,
                        website_profile=website_profile,
                        database=database,
                        keyword_limit=fallback_keyword_limit,
                        reason=error.reason,
                        detail=error.message,
                    )
                live_failure_reason = f"Live SEMrush was unavailable ({error.reason}). Manual upload fallback was used."
            else:
                live_failure_reason = ""
        else:
            live_failure_reason = (
                "MODULE0_FORCE_MOCK_SEMRUSH is enabled."
                if self.force_mock_semrush
                else "SEMRUSH_API_KEY is not configured or credits are unavailable."
            )

        if manual_keyword_file_meta is not None and manual_keyword_content is not None:
            try:
                upload_result = self.manual_keyword_upload_processor.process(
                    filename=manual_keyword_file_meta.filename,
                    content=manual_keyword_content,
                    request=request,
                    site_classification=site_classification,
                    website_profile=website_profile,
                    keyword_limit=fallback_keyword_limit,
                )
            except Exception as error:
                return self._fallback_result(
                    request=request,
                    cdd_extraction=cdd_extraction,
                    site_classification=site_classification,
                    website_profile=website_profile,
                    database=database,
                    keyword_limit=fallback_keyword_limit,
                    reason="manual_upload_parse_error",
                    detail=(
                        f"Manual SEMrush keyword upload '{manual_keyword_file_meta.filename}' could not be parsed: "
                        f"{error.__class__.__name__}."
                    ),
                )
            if upload_result.accepted_keywords:
                keywords = [
                    SEMrushKeywordRecord(
                        keyword=item.keyword,
                        search_volume=item.search_volume,
                        keyword_difficulty=item.keyword_difficulty,
                        current_position=item.current_position,
                        source="semrush_manual_upload",
                        cpc=item.cpc,
                        mapped_url=item.mapped_url,
                        confidence_score=item.confidence_score,
                        quality_score=item.quality_score,
                        is_estimated=False,
                        notes=item.notes,
                    )
                    for item in upload_result.accepted_keywords
                ]
                competitors = self._build_fallback_competitors(request, cdd_extraction, keywords)
                estimated_traffic = max(
                    50,
                    int(sum(keyword.search_volume for keyword in keywords[:20]) * 0.07),
                )
                notes = [
                    "Live SEMrush API data was not available, so a manually uploaded SEMrush keyword export was used.",
                    f"Uploaded keyword file parsed via {upload_result.parser_used}.",
                    *upload_result.notes,
                ]
                if live_failure_reason:
                    notes.insert(1, live_failure_reason)
                snapshot = SEMrushSnapshot(
                    configured=bool(self.api_key),
                    region_database=database,
                    status="manual_upload",
                    data_source="semrush_manual_upload",
                    fallback_used=True,
                    is_estimated=False,
                    warning_message="Live SEMrush API was unavailable. Uploaded SEMrush keyword export was used for this run.",
                    keyword_limit=fallback_keyword_limit,
                    notes=notes,
                    estimated_monthly_traffic=estimated_traffic,
                    estimated_monthly_traffic_history=[estimated_traffic],
                    organic_keyword_count=len(keywords),
                    competitors_evaluated=len(competitors),
                    source_file_name=upload_result.file_name,
                    source_file_extension=manual_keyword_file_meta.extension,
                    raw_keyword_rows=upload_result.raw_rows,
                    accepted_keyword_rows=len(upload_result.accepted_keywords),
                    rejected_keyword_rows=len(upload_result.rejected_keywords),
                    rejected_keyword_examples=[
                        f"{item.keyword} ({item.reason})"
                        for item in upload_result.rejected_keywords[:10]
                    ],
                )
                return SEMrushCollectionResult(
                    snapshot=snapshot,
                    keywords=keywords,
                    competitors=competitors,
                )

            return self._fallback_result(
                request=request,
                cdd_extraction=cdd_extraction,
                site_classification=site_classification,
                website_profile=website_profile,
                database=database,
                keyword_limit=fallback_keyword_limit,
                reason="manual_upload_filtered_empty",
                detail=(
                    f"The uploaded SEMrush file '{manual_keyword_file_meta.filename}' was parsed, "
                    "but no business-aligned keywords survived filtering."
                ),
            )

        return self._fallback_result(
            request=request,
            cdd_extraction=cdd_extraction,
            site_classification=site_classification,
            website_profile=website_profile,
            database=database,
            keyword_limit=fallback_keyword_limit,
            reason="forced_mock" if self.force_mock_semrush else "missing_api_key",
            detail=live_failure_reason,
        )

    def _fetch_domain_overview(
        self,
        client: httpx.Client,
        domain: str,
        database: str,
    ) -> int | None:
        rows = self._request_csv(
            client=client,
            params={
                "type": "domain_rank",
                "domain": domain,
                "database": database,
                "display_limit": 1,
                "export_columns": "Dn,Ot,Or",
            },
        )
        if not rows:
            raise SEMrushAPIError("empty_response", "SEMrush overview report returned no data.")

        traffic = rows[0].get("Ot")
        if not traffic:
            return None
        return self._to_int(traffic)

    def _fetch_domain_keywords(
        self,
        client: httpx.Client,
        domain: str,
        database: str,
        keyword_limit: int,
    ) -> list[SEMrushKeywordRecord]:
        rows = self._request_csv(
            client=client,
            params={
                "type": "domain_organic",
                "domain": domain,
                "database": database,
                "display_limit": keyword_limit,
                "display_sort": "tr_desc",
                "export_columns": "Ph,Po,Nq,Kd,Cp",
            },
        )
        return [
            SEMrushKeywordRecord(
                keyword=row.get("Ph", "").strip(),
                current_position=self._to_optional_int(row.get("Po")),
                search_volume=self._to_int(row.get("Nq")),
                keyword_difficulty=self._to_int(row.get("Kd")),
                source="semrush",
                cpc=self._to_optional_float(row.get("Cp")),
                confidence_score=0.95,
                quality_score=0.92,
                is_estimated=False,
            )
            for row in rows
            if row.get("Ph")
        ]

    def _fetch_competitors(
        self,
        client: httpx.Client,
        domain: str,
        database: str,
    ) -> list[SEMrushCompetitorRecord]:
        rows = self._request_csv(
            client=client,
            params={
                "type": "domain_organic_organic",
                "domain": domain,
                "database": database,
                "display_limit": self.competitor_limit,
                "display_sort": "cr_desc",
                "export_columns": "Dn,Cr,Np",
            },
        )

        competitors: list[SEMrushCompetitorRecord] = []
        for row in rows[: self.competitor_limit]:
            competitor_domain = row.get("Dn", "").strip()
            if not competitor_domain:
                continue
            keyword_rows = self._fetch_domain_keywords(
                client=client,
                domain=competitor_domain,
                database=database,
                keyword_limit=self.competitor_keyword_limit,
            )
            competitors.append(
                SEMrushCompetitorRecord(
                    domain=competitor_domain,
                    competition_level=self._to_optional_float(row.get("Cr")),
                    shared_keywords=self._to_optional_int(row.get("Np")),
                    keyword_sample=[item.keyword for item in keyword_rows[:10]],
                    name=competitor_domain,
                    reason_for_selection="Returned by SEMrush organic competitor report.",
                    likely_services=[],
                    content_gaps=[],
                    service_gaps=[],
                    estimated_strength=self._strength_from_metrics(
                        self._to_optional_float(row.get("Cr")),
                        self._to_optional_int(row.get("Np")),
                    ),
                    confidence_score=0.9,
                    is_estimated=False,
                    source="semrush",
                )
            )
        return competitors

    def _request_csv(self, client: httpx.Client, params: dict[str, Any]) -> list[dict[str, str]]:
        request_params = {
            "key": self.api_key,
            "export_escape": 1,
            **params,
        }
        try:
            response = client.get(self.BASE_URL, params=request_params)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise SEMrushAPIError("timeout", "SEMrush request timed out.") from error
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status == 403:
                raise SEMrushAPIError("403", "SEMrush returned 403.") from error
            raise SEMrushAPIError("api_access_error", f"SEMrush returned HTTP {status}.") from error
        except httpx.HTTPError as error:
            raise SEMrushAPIError("api_access_error", "SEMrush request failed.") from error

        body = response.text.strip()
        if not body:
            raise SEMrushAPIError("empty_response", "SEMrush returned an empty response.")
        if body.startswith("ERROR"):
            raise SEMrushAPIError(self._classify_error(body), body)

        return self._parse_csv_rows(body)

    def _parse_csv_rows(self, body: str) -> list[dict[str, str]]:
        reader = csv.DictReader(io.StringIO(body), delimiter=";")
        return [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]

    def _fallback_result(
        self,
        request: Module0Request,
        cdd_extraction: CDDExtraction | None,
        site_classification: SiteClassification | None,
        website_profile: WebsiteProfile | None,
        database: str,
        keyword_limit: int,
        reason: str,
        detail: str,
    ) -> SEMrushCollectionResult:
        fallback_notes = [FALLBACK_WARNING, f"Fallback reason: {reason}.", detail]
        data_source = "mock_fallback"
        keywords = []
        competitors: list[SEMrushCompetitorRecord] = []
        status = "credits_unavailable" if reason in {"missing_api_key", "credits", "forced_mock"} else "fallback"

        try:
            openai_result = self.openai_fallback_service.generate(
                request=request,
                cdd_extraction=cdd_extraction,
                site_classification=site_classification,
                website_profile=website_profile,
                keyword_limit=keyword_limit,
                competitor_limit=self.competitor_limit,
            )
            keywords = [
                SEMrushKeywordRecord(
                    keyword=item.keyword,
                    search_volume=item.search_volume,
                    keyword_difficulty=item.keyword_difficulty,
                    current_position=item.current_position,
                    source="openai_mock_fallback",
                    cpc=item.cpc,
                    intent=item.intent,
                    priority=item.priority,
                    mapped_url=item.mapped_url,
                    ai_answer_trigger_rate=item.ai_answer_trigger_rate,
                    confidence_score=item.confidence_score,
                    quality_score=item.quality_score,
                    is_estimated=True,
                    notes=item.notes,
                )
                for item in openai_result.keywords
            ]
            competitors = [
                SEMrushCompetitorRecord(
                    domain=item.domain,
                    competition_level=round(item.estimated_strength / 100, 2),
                    shared_keywords=None,
                    keyword_sample=item.keyword_sample,
                    name=item.name,
                    reason_for_selection=item.reason_for_selection,
                    likely_services=item.likely_services,
                    content_gaps=item.content_gaps,
                    service_gaps=item.service_gaps,
                    estimated_strength=item.estimated_strength,
                    confidence_score=item.confidence_score,
                    is_estimated=True,
                    source="openai_mock_fallback",
                    notes=item.notes,
                )
                for item in openai_result.competitors
            ]
            supplemental_competitors = self._input_competitor_candidates(request, cdd_extraction)
            competitors = self._merge_competitors(
                competitors,
                supplemental_competitors,
                limit=self.competitor_limit,
            )
            data_source = "openai_mock_fallback"
            fallback_notes.extend(
                [
                    "OpenAI generated estimated fallback keyword data for this run.",
                    f"OpenAI fallback model: {self.openai_fallback_service.model}.",
                    *openai_result.notes,
                ]
            )
        except OpenAIFallbackError as error:
            fallback_notes.extend(
                [
                    f"OpenAI fallback unavailable: {error.reason}.",
                    error.message,
                    "Deterministic synthetic fallback was used as the final fallback layer.",
                ]
            )
            keywords = self._generate_mock_keywords(
                request,
                website_profile=website_profile,
                keyword_limit=keyword_limit,
            )
            competitors = self._build_fallback_competitors(request, cdd_extraction, keywords)

        estimated_traffic = max(
            50,
            int(sum(keyword.search_volume for keyword in keywords[:20]) * 0.07),
        )
        if not competitors:
            competitors = self._build_fallback_competitors(request, cdd_extraction, keywords)
        snapshot = SEMrushSnapshot(
            configured=bool(self.api_key),
            region_database=database,
            status=status,
            data_source=data_source,
            fallback_used=True,
            is_estimated=True,
            warning_message=FALLBACK_WARNING,
            keyword_limit=keyword_limit,
            notes=fallback_notes,
            estimated_monthly_traffic=estimated_traffic,
            estimated_monthly_traffic_history=[estimated_traffic],
            organic_keyword_count=len(keywords),
            competitors_evaluated=len(competitors),
        )
        return SEMrushCollectionResult(
            snapshot=snapshot,
            keywords=keywords,
            competitors=competitors,
        )

    def _generate_mock_keywords(
        self,
        request: Module0Request,
        website_profile: WebsiteProfile | None,
        keyword_limit: int,
    ) -> list[SEMrushKeywordRecord]:
        services = self._fallback_service_phrases(request, website_profile)
        locations = [item.strip() for item in request.target_locations if item.strip()]
        if not services:
            services = ["local service"]
        if not locations:
            locations = ["melbourne"]

        templates = [
            "{service} {location}",
            "{service} cost",
            "{service} cost {location}",
            "{service} quote",
            "commercial {service} {location}",
            "emergency {service}",
            "how much does {service} cost",
            "how much does {service} cost in {location}",
        ]

        seen: set[str] = set()
        records: list[SEMrushKeywordRecord] = []
        for service in services:
            for location in locations:
                for template in templates:
                    keyword = template.format(service=service, location=location).strip().lower()
                    keyword = re.sub(r"\s+", " ", keyword)
                    if not self._is_quality_fallback_keyword(keyword) or keyword in seen:
                        continue
                    seen.add(keyword)
                    records.append(self._build_mock_keyword(keyword))
                    if len(records) >= keyword_limit:
                        return records
        return records[:keyword_limit]

    def _build_mock_keyword(self, keyword: str) -> SEMrushKeywordRecord:
        digest = hashlib.sha256(keyword.encode("utf-8")).hexdigest()
        volume = 20 + (int(digest[:6], 16) % 480)
        difficulty = 12 + (int(digest[6:10], 16) % 55)
        position = 1 + (int(digest[10:14], 16) % 30)
        cpc = round(0.5 + ((int(digest[14:18], 16) % 900) / 100), 2)
        return SEMrushKeywordRecord(
            keyword=keyword,
            search_volume=volume,
            keyword_difficulty=min(difficulty, 100),
            current_position=position,
            source="semrush-mock-fallback",
            cpc=cpc,
            confidence_score=0.3,
            quality_score=0.2,
            is_estimated=True,
        )

    def _fallback_service_phrases(
        self,
        request: Module0Request,
        website_profile: WebsiteProfile | None,
    ) -> list[str]:
        phrases: list[str] = []
        seen: set[str] = set()

        location_tokens = {
            token
            for value in request.target_locations
            for token in re.split(r"\W+", value.lower())
            if token and len(token) > 2
        }

        def add_phrase(value: str) -> None:
            cleaned = re.sub(r"[^a-z0-9\s]", " ", value.lower())
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            tokens = [
                token
                for token in cleaned.split()
                if len(token) > 2 and token not in {"pty", "ltd", "llc", "inc", "group", "co", "location", "locations"}
            ]
            if location_tokens:
                filtered = [token for token in tokens if token not in location_tokens]
                if len(filtered) >= 2:
                    tokens = filtered
            cleaned = " ".join(tokens[:5])
            if len(cleaned.split()) < 2 or cleaned in seen:
                return
            seen.add(cleaned)
            phrases.append(cleaned)

        for value in [*request.services_or_products, *request.priority_services]:
            add_phrase(value)
        add_phrase(request.brand_name)
        if website_profile is not None:
            add_phrase(website_profile.homepage_title or "")
            add_phrase(website_profile.meta_description or "")
            for title in website_profile.sample_page_titles:
                add_phrase(title)
            for url in website_profile.url_inventory.service_like_urls[:10]:
                add_phrase(url.rsplit("/", 1)[-1].replace("-", " "))
            excerpt = website_profile.homepage_text_excerpt or ""
            for chunk in excerpt.split("."):
                add_phrase(chunk)
        return phrases[:10]

    def _is_quality_fallback_keyword(self, keyword: str) -> bool:
        lowered = keyword.lower()
        tokens = [token for token in re.split(r"\W+", lowered) if token]
        meaningful = [token for token in tokens if len(token) > 2]
        if len(tokens) < 2 or len(meaningful) > 6:
            return False
        if re.search(r"\b\d+\b$", lowered):
            return False
        if any(token in lowered for token in {"keyword ", ".com", ".au", " brand ", " company"}):
            return False
        if len(set(meaningful)) <= 1:
            return False
        if {token for token in meaningful if meaningful.count(token) > 1}:
            return False
        if self._has_stacked_quality_modifiers(tokens):
            return False
        if len(meaningful) > 6 and not lowered.startswith(("how ", "what ", "why ", "who ", "where ", "when ", "is ", "do ", "does ", "can ", "should ")):
            return False
        return True

    def _has_stacked_quality_modifiers(self, tokens: list[str]) -> bool:
        modifier_tokens = [token for token in tokens if len(token) > 1]
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

    def _build_fallback_competitors(
        self,
        request: Module0Request,
        cdd_extraction: CDDExtraction | None,
        keywords: list[SEMrushKeywordRecord],
    ) -> list[SEMrushCompetitorRecord]:
        candidates = self._input_competitor_candidates(request, cdd_extraction)
        if candidates:
            for index, competitor in enumerate(candidates[: self.competitor_limit], start=1):
                competitor.competition_level = round(0.42 + (index * 0.09), 2)
                competitor.shared_keywords = 10 + index * 5
                competitor.estimated_strength = min(100, 40 + index * 12)
                competitor.keyword_sample = [item.keyword for item in keywords[index - 1 : index + 7]]
            return candidates[: self.competitor_limit]

        return self._generate_placeholder_competitors(request, keywords)

    def _input_competitor_candidates(
        self,
        request: Module0Request,
        cdd_extraction: CDDExtraction | None,
    ) -> list[SEMrushCompetitorRecord]:
        own_domain = self._normalize_domain(request)
        candidates: list[SEMrushCompetitorRecord] = []
        seen: set[str] = set()

        def add_candidate(label: str, source: str, note: str) -> None:
            normalized = self._normalize_candidate(label)
            if (
                not normalized
                or not self._looks_like_domain(normalized)
                or normalized == own_domain
                or normalized in seen
            ):
                return
            seen.add(normalized)
            candidates.append(
                SEMrushCompetitorRecord(
                    domain=normalized,
                    competition_level=None,
                    shared_keywords=None,
                    keyword_sample=[],
                    name=self._display_name_from_domain(normalized),
                    reason_for_selection="Fallback competitor extracted from available project inputs.",
                    likely_services=[],
                    content_gaps=[],
                    service_gaps=[],
                    estimated_strength=0,
                    confidence_score=0.45,
                    is_estimated=True,
                    source=source,
                    notes=[note],
                )
            )

        for competitor in request.known_competitors:
            add_candidate(
                competitor,
                source="frontend_known_competitor",
                note="Fallback competitor provided from frontend onboarding input.",
            )

        if cdd_extraction is not None:
            for competitor in cdd_extraction.competitor_hints:
                source = "cdd_domain" if self._looks_like_domain(competitor) else "cdd_competitor_hint"
                add_candidate(
                    competitor,
                    source=source,
                    note="Fallback competitor extracted from the uploaded CDD.",
                )

        return candidates

    def _merge_competitors(
        self,
        primary: list[SEMrushCompetitorRecord],
        supplemental: list[SEMrushCompetitorRecord],
        limit: int,
    ) -> list[SEMrushCompetitorRecord]:
        merged: list[SEMrushCompetitorRecord] = []
        seen: set[str] = set()
        for candidate in [*primary, *supplemental]:
            if candidate.domain in seen:
                continue
            seen.add(candidate.domain)
            merged.append(candidate)
            if len(merged) >= limit:
                break
        return merged

    def _generate_placeholder_competitors(
        self,
        request: Module0Request,
        keywords: list[SEMrushKeywordRecord],
    ) -> list[SEMrushCompetitorRecord]:
        domain = self._normalize_domain(request)
        hostname = domain.split(".")[0]
        competitors: list[SEMrushCompetitorRecord] = []
        for index in range(1, min(self.competitor_limit, 5) + 1):
            competitors.append(
                SEMrushCompetitorRecord(
                    domain=f"{hostname}-competitor-{index}.com.au",
                    competition_level=round(0.4 + (index * 0.08), 2),
                    shared_keywords=12 + index * 4,
                    keyword_sample=[item.keyword for item in keywords[index - 1 : index + 7]],
                    name=f"{hostname} competitor {index}",
                    reason_for_selection="Placeholder competitor generated because no real competitor hints were available.",
                    likely_services=[],
                    content_gaps=[],
                    service_gaps=[],
                    estimated_strength=min(100, 35 + index * 10),
                    confidence_score=0.15,
                    is_estimated=True,
                    source="mock_placeholder",
                    notes=["Placeholder competitor generated because no real competitor hints were available."],
                )
            )
        return competitors

    def _looks_like_domain(self, value: str) -> bool:
        return "." in value and " " not in value

    def _normalize_candidate(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.split("/")[0].strip().lower()
        if cleaned.startswith("www."):
            cleaned = cleaned[4:]
        return cleaned

    def _display_name_from_domain(self, value: str) -> str:
        root = value.split(".")[0]
        tokens = [token for token in re.split(r"[-_]+", root) if token]
        return " ".join(token.capitalize() for token in tokens[:6]) or value

    def _classify_error(self, body: str) -> str:
        lowered = body.lower()
        if any(token in lowered for token in ["not enough", "units", "quota", "balance"]):
            return "credits"
        if "403" in lowered:
            return "403"
        if any(token in lowered for token in ["api key", "access", "forbidden", "permission"]):
            return "api_access_error"
        return "api_error"

    def _get_client(self) -> httpx.Client:
        if self.http_client is not None:
            return _SharedClientContext(self.http_client)
        return httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0))

    def _normalize_domain(self, request: Module0Request) -> str:
        domain = request.domain or (urlparse(str(request.website_url)).netloc or "")
        normalized = domain.lower().strip()
        if normalized.startswith("www."):
            normalized = normalized[4:]
        return normalized

    def _resolve_keyword_limit(self) -> int:
        if self.environment in {"production", "prod"}:
            return self.production_keyword_limit
        return self.test_keyword_limit

    def _to_int(self, value: str | None) -> int:
        if not value:
            return 0
        normalized = str(value).strip().replace(",", "")
        try:
            return int(float(normalized))
        except ValueError:
            digits = "".join(char for char in normalized if char.isdigit())
            return int(digits or "0")

    def _to_optional_int(self, value: str | None) -> int | None:
        number = self._to_int(value)
        return number or None

    def _to_optional_float(self, value: str | None) -> float | None:
        if value in (None, ""):
            return None
        normalized = str(value).strip().replace(",", "")
        try:
            return float(normalized)
        except ValueError:
            return None

    def _parse_positive_int(self, value: str | None, default: int) -> int:
        try:
            parsed = int(value or default)
        except ValueError:
            return default
        return parsed if parsed > 0 else default

    def _parse_bool(self, value: str | None, default: bool) -> bool:
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _strength_from_metrics(self, competition_level: float | None, shared_keywords: int | None) -> int:
        base = int((competition_level or 0.0) * 100)
        shared_boost = min(shared_keywords or 0, 20)
        return max(0, min(100, base + shared_boost))


class _SharedClientContext:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False
