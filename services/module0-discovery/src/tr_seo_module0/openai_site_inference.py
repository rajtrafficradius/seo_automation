from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from tr_seo_contracts.module0 import BusinessType, Module0Request, SiteClassification, WebsiteProfile


class OpenAISiteInferenceError(Exception):
    pass


@dataclass(slots=True)
class OpenAISiteInferenceResult:
    business_type: BusinessType | None = None
    industry_category: str | None = None
    geographic_target: str | None = None
    language: str | None = None
    active_components: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    confidence_score: float = 0.0


class OpenAISiteInferenceService:
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

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def infer(
        self,
        request: Module0Request,
        site_classification: SiteClassification,
        website_profile: WebsiteProfile,
    ) -> OpenAISiteInferenceResult:
        if not self.api_key:
            raise OpenAISiteInferenceError("OPENAI_API_KEY is not configured.")

        payload = self._build_payload(request, site_classification, website_profile)
        try:
            with self._client() as client:
                response = client.post(
                    self.BASE_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as error:  # pragma: no cover - network path
            raise OpenAISiteInferenceError(f"OpenAI site inference request failed: {error.__class__.__name__}") from error

        try:
            content = self._extract_content(response.json())
            parsed = json.loads(content)
        except Exception as error:  # pragma: no cover - malformed provider response
            raise OpenAISiteInferenceError("OpenAI site inference returned invalid JSON.") from error

        business_type_value = str(parsed.get("business_type") or "").strip().lower()
        business_type = None
        if business_type_value in {item.value for item in BusinessType}:
            business_type = BusinessType(business_type_value)

        return OpenAISiteInferenceResult(
            business_type=business_type,
            industry_category=self._clean_value(parsed.get("industry_category")),
            geographic_target=self._clean_value(parsed.get("geographic_target")),
            language=self._clean_value(parsed.get("language")),
            active_components=self._clean_list(parsed.get("active_components")),
            notes=self._clean_list(parsed.get("notes"), limit=8),
            confidence_score=self._to_probability(parsed.get("confidence_score"), 0.72),
        )

    def _build_payload(
        self,
        request: Module0Request,
        site_classification: SiteClassification,
        website_profile: WebsiteProfile,
    ) -> dict[str, Any]:
        user_payload = {
            "task": "Refine website business classification using accessible public signals only.",
            "rules": [
                "Do not invent inaccessible website details.",
                "Use the most probable business interpretation from titles, headings, schema, navigation, URL structure, and services.",
                "Return structured JSON only.",
                "Prefer actionable component labels like category_product_model, service_content_model, faq_content, trust_pages, location_pages, content_hub.",
            ],
            "inputs": {
                "brand_name": request.brand_name,
                "target_country": request.target_country,
                "services_or_products": request.services_or_products,
                "priority_services": request.priority_services,
                "target_locations": request.target_locations,
                "business_goals": request.business_goals,
                "heuristic_business_type": site_classification.business_type.value,
                "heuristic_industry_category": site_classification.industry_category,
                "heuristic_geographic_target": site_classification.geographic_target,
                "heuristic_language": site_classification.language,
                "heuristic_active_components": site_classification.active_components,
                "homepage_title": website_profile.homepage_title,
                "meta_description": website_profile.meta_description,
                "homepage_text_excerpt": website_profile.homepage_text_excerpt,
                "sample_page_titles": website_profile.sample_page_titles[:10],
                "observed_headings": website_profile.observed_headings[:15],
                "navigation_labels": website_profile.navigation_labels[:15],
                "service_terminology": website_profile.service_terminology[:15],
                "schema_types": website_profile.detected_schema_types,
                "sample_urls": website_profile.url_inventory.sample_urls[:18],
                "service_like_urls": website_profile.url_inventory.service_like_urls[:18],
                "location_like_urls": website_profile.url_inventory.location_like_urls[:12],
            },
            "output_schema": {
                "business_type": "service | ecommerce | saas | local | hybrid | unknown",
                "industry_category": "specific industry category",
                "geographic_target": "market scope",
                "language": "language code or language label",
                "active_components": ["component labels"],
                "notes": ["reasoning notes"],
                "confidence_score": "0 to 1",
            },
        }
        return {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You refine website business classification for a production SEO system using public crawl evidence. "
                        "Do not return prose outside JSON."
                    ),
                },
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        }

    def _extract_content(self, body: dict[str, Any]) -> str:
        choices = body.get("choices", [])
        if not choices:
            return "{}"
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, str):
            return content
        return "{}"

    def _clean_value(self, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None

    def _clean_list(self, values: Any, limit: int = 10) -> list[str]:
        if not isinstance(values, list):
            return []
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = str(value or "").strip()
            lowered = cleaned.lower()
            if not cleaned or lowered in seen:
                continue
            seen.add(lowered)
            result.append(cleaned)
            if len(result) >= limit:
                break
        return result

    def _to_probability(self, value: Any, default: float) -> float:
        try:
            parsed = float(str(value).strip())
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, parsed))

    def _client(self):
        if self.http_client is not None:
            return _SharedClientContext(self.http_client)
        return httpx.Client(timeout=httpx.Timeout(25.0, connect=10.0))


class _SharedClientContext:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False
