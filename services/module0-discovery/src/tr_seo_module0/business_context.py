from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlparse

from tr_seo_contracts.module0 import BusinessType, Module0Request, SiteClassification, WebsiteProfile


TOKEN_MAP = {
    "replacements": "replacement",
    "repairs": "repair",
    "installations": "installation",
    "prices": "price",
    "quotes": "quote",
    "gutters": "gutter",
    "downpipes": "downpipe",
}

GENERIC_STOP_TOKENS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "for",
    "to",
    "in",
    "on",
    "at",
    "with",
    "by",
    "from",
    "our",
    "your",
    "their",
    "my",
}

QUESTION_TOKENS = {
    "how",
    "what",
    "why",
    "when",
    "who",
    "where",
    "does",
    "do",
    "did",
    "can",
    "should",
    "is",
    "are",
    "much",
}

COMMERCIAL_MODIFIER_TOKENS = {
    "cost",
    "quote",
    "price",
    "pricing",
    "near",
    "me",
    "best",
    "cheap",
    "affordable",
    "review",
    "reviews",
    "company",
    "specialist",
    "specialists",
    "professional",
    "professionals",
    "expert",
    "experts",
    "offers",
}

NAVIGATION_TOKENS = {
    "about",
    "contact",
    "gallery",
    "home",
    "homepage",
    "blog",
    "blogs",
    "news",
    "article",
    "articles",
    "resource",
    "resources",
    "faq",
    "faqs",
    "terms",
    "privacy",
    "policy",
    "login",
    "account",
    "cart",
    "checkout",
    "showroom",
    "page",
    "pages",
    "menu",
    "navigation",
}

NOISE_TOKENS = {
    "observed",
    "urls",
    "url",
    "safe",
    "crawl",
    "signal",
    "signals",
    "preview",
    "summary",
    "section",
    "sections",
    "detected",
    "public",
    "profile",
    "module",
    "onboarding",
}

SERVICE_TOKENS = {
    "repair",
    "replacement",
    "installation",
    "install",
    "maintenance",
    "service",
    "services",
    "fitout",
    "consulting",
    "cleaning",
    "supply",
    "supply",
}

ECOMMERCE_TOKENS = {
    "product",
    "products",
    "category",
    "categories",
    "collection",
    "collections",
    "shop",
    "buy",
    "furniture",
    "chair",
    "chairs",
    "table",
    "tables",
    "desk",
    "desks",
    "bed",
    "beds",
    "sofa",
    "sofas",
    "storage",
    "seating",
}

INDUSTRY_TOKEN_MAP = {
    "roofing_and_guttering": {
        "gutter",
        "downpipe",
        "fascia",
        "roof",
        "roofing",
        "guttering",
        "colorbond",
        "box",
        "quad",
        "rainwater",
    },
    "healthcare_and_commercial_furniture": {
        "healthcare",
        "commercial",
        "furniture",
        "chair",
        "seating",
        "storage",
        "table",
        "desk",
        "aged",
        "care",
        "hospital",
        "clinic",
    },
    "commercial_furniture": {
        "commercial",
        "furniture",
        "chair",
        "seating",
        "storage",
        "table",
        "desk",
        "office",
    },
    "trade_services": {
        "electrician",
        "electrical",
        "plumber",
        "plumbing",
        "repair",
        "replacement",
        "installation",
        "maintenance",
    },
    "digital_marketing": {
        "seo",
        "marketing",
        "agency",
        "digital",
        "strategy",
        "google",
        "ads",
        "content",
    },
    "software_and_saas": {
        "software",
        "platform",
        "saas",
        "app",
        "automation",
        "tool",
        "tools",
        "system",
    },
}

ALLOWED_QUERY_TOKENS = {
    "emergency",
    "commercial",
    "residential",
    "local",
    "same",
    "day",
    "melbourne",
    "sydney",
    "brisbane",
    "perth",
    "adelaide",
    "richmond",
    "kew",
    "hawthorn",
    "installation",
    "repair",
    "replacement",
    "cost",
    "quote",
    "price",
}


@dataclass(slots=True)
class BusinessContextProfile:
    business_type: BusinessType
    industry_category: str
    service_phrases: list[str] = field(default_factory=list)
    service_tokens: set[str] = field(default_factory=set)
    commerce_tokens: set[str] = field(default_factory=set)
    industry_tokens: set[str] = field(default_factory=set)
    location_tokens: set[str] = field(default_factory=set)
    context_tokens: set[str] = field(default_factory=set)
    dynamic_stop_tokens: set[str] = field(default_factory=set)
    brand_tokens: set[str] = field(default_factory=set)


class BusinessContextAnalyzer:
    def build(
        self,
        *,
        request: Module0Request | None = None,
        site_classification: SiteClassification | None = None,
        website_profile: WebsiteProfile | None = None,
        business_type: BusinessType | None = None,
        brand_name: str = "",
        target_locations: list[str] | None = None,
        services_or_products: list[str] | None = None,
        existing_urls: list[str] | None = None,
    ) -> BusinessContextProfile:
        request_services = list(services_or_products or [])
        request_locations = list(target_locations or [])
        resolved_brand = brand_name
        resolved_business_type = business_type or BusinessType.UNKNOWN
        industry_category = "general_business_services"

        if request is not None:
            request_services = [*request.services_or_products, *request.priority_services, *request_services]
            request_locations = [*request.target_locations, *request_locations]
            resolved_brand = resolved_brand or request.brand_name
            resolved_business_type = (
                request.business_type
                if request.business_type != BusinessType.UNKNOWN
                else resolved_business_type
            )
        if site_classification is not None:
            if resolved_business_type == BusinessType.UNKNOWN:
                resolved_business_type = site_classification.business_type
            industry_category = site_classification.industry_category or industry_category
        location_tokens = {
            token
            for value in request_locations
            for token in self._tokenize(value)
            if token not in GENERIC_STOP_TOKENS
        }

        phrase_scores: dict[str, float] = {}
        navigation_tokens: set[str] = set()
        context_tokens: set[str] = set()
        industry_tokens = set(INDUSTRY_TOKEN_MAP.get(industry_category, set()))
        semantic_seed_tokens = {
            token
            for value in request_services
            for token in self._tokenize(value)
            if token not in GENERIC_STOP_TOKENS
        } | set(industry_tokens)
        if website_profile is not None:
            for value in [*website_profile.sample_page_titles[:12], *website_profile.service_terminology[:18]]:
                semantic_seed_tokens.update(
                    token
                    for token in self._tokenize(value)
                    if token not in GENERIC_STOP_TOKENS and token not in QUESTION_TOKENS
                )
            for url in website_profile.url_inventory.service_like_urls[:24]:
                for phrase in self._phrases_from_url(url):
                    semantic_seed_tokens.update(
                        token
                        for token in self._tokenize(phrase)
                        if token not in GENERIC_STOP_TOKENS and token not in QUESTION_TOKENS
                    )
        raw_brand_tokens = self._token_set(resolved_brand)
        brand_tokens = {
            token
            for token in raw_brand_tokens
            if token not in SERVICE_TOKENS
            and token not in ECOMMERCE_TOKENS
            and token not in industry_tokens
            and token not in location_tokens
            and token not in semantic_seed_tokens
        }

        for phrase in request_services:
            self._add_phrase(phrase_scores, phrase, 4.0, brand_tokens, location_tokens)

        if website_profile is not None:
            for phrase in website_profile.service_terminology[:18]:
                self._add_phrase(phrase_scores, phrase, 3.8, brand_tokens, location_tokens)
            for title in website_profile.sample_page_titles[:12]:
                self._add_phrase_parts(phrase_scores, title, 2.4, brand_tokens, location_tokens)
            for heading in website_profile.observed_headings[:20]:
                self._add_phrase_parts(phrase_scores, heading, 2.2, brand_tokens, location_tokens)
            for url in website_profile.url_inventory.service_like_urls[:24]:
                for phrase in self._phrases_from_url(url):
                    self._add_phrase(phrase_scores, phrase, 2.8, brand_tokens, location_tokens)
            for url in website_profile.url_inventory.sample_urls[:24]:
                for phrase in self._phrases_from_url(url):
                    self._add_phrase(phrase_scores, phrase, 1.6, brand_tokens, location_tokens)
            for phrase in self._phrases_from_excerpt(website_profile.homepage_text_excerpt or ""):
                self._add_phrase(phrase_scores, phrase, 1.9, brand_tokens, location_tokens)
            for label in website_profile.navigation_labels[:24]:
                navigation_tokens.update(self._tokenize(label))
            for schema in website_profile.detected_schema_types:
                context_tokens.update(self._tokenize(schema))

        for url in existing_urls or []:
            for phrase in self._phrases_from_url(url):
                self._add_phrase(phrase_scores, phrase, 1.8, brand_tokens, location_tokens)

        service_phrases = [
            phrase
            for phrase, _score in sorted(
                phrase_scores.items(),
                key=lambda item: (-item[1], -len(item[0].split()), item[0]),
            )
        ][:24]

        service_tokens = {
            token
            for phrase in service_phrases
            for token in self._tokenize(phrase)
            if token not in GENERIC_STOP_TOKENS
            and token not in QUESTION_TOKENS
            and token not in COMMERCIAL_MODIFIER_TOKENS
            and token not in NAVIGATION_TOKENS
            and token not in NOISE_TOKENS
            and token not in {"service", "services", "product", "products", "category", "categories", "collection", "collections"}
            and token not in location_tokens
            and token not in brand_tokens
        }
        service_tokens.update(industry_tokens)
        commerce_tokens = {
            token
            for token in service_tokens
            if token in ECOMMERCE_TOKENS or resolved_business_type in {BusinessType.ECOMMERCE, BusinessType.HYBRID}
        }

        for phrase in service_phrases:
            context_tokens.update(self._tokenize(phrase))
        context_tokens.update(service_tokens)
        context_tokens.update(location_tokens)
        dynamic_stop_tokens = {
            token
            for token in navigation_tokens
            if token in NAVIGATION_TOKENS or token in NOISE_TOKENS or token in {"menu", "shop", "catalog"}
        }

        return BusinessContextProfile(
            business_type=resolved_business_type,
            industry_category=industry_category,
            service_phrases=service_phrases,
            service_tokens=service_tokens,
            commerce_tokens=commerce_tokens,
            industry_tokens=industry_tokens,
            location_tokens=location_tokens,
            context_tokens=context_tokens,
            dynamic_stop_tokens=dynamic_stop_tokens,
            brand_tokens=brand_tokens,
        )

    def normalize_query(self, value: str, context: BusinessContextProfile) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())
        tokens = [TOKEN_MAP.get(token, token) for token in cleaned.split() if token]
        filtered = [token for token in tokens if token not in context.brand_tokens]
        return re.sub(r"\s+", " ", " ".join(filtered)).strip()

    def naturalness_score(self, value: str, context: BusinessContextProfile) -> float:
        keyword = self.normalize_query(value, context)
        tokens = [token for token in keyword.split() if token]
        if not tokens:
            return 0.0
        meaningful = [
            token
            for token in tokens
            if token not in GENERIC_STOP_TOKENS and token not in context.location_tokens
        ]
        score = 0.15
        if 2 <= len(meaningful) <= 6:
            score += 0.22
        elif self._is_question_like(keyword) and len(meaningful) <= 8:
            score += 0.18
        else:
            score -= 0.18
        if not self._has_repeated_tokens(tokens):
            score += 0.12
        if not self._has_stacked_modifiers(tokens):
            score += 0.12
        if not self._looks_like_fragment(keyword, tokens):
            score += 0.16
        overlap = len(set(meaningful) & context.context_tokens)
        if overlap:
            score += min(0.2, overlap * 0.05)
        unknown_ratio = self._unknown_token_ratio(tokens, context)
        if unknown_ratio <= 0.25:
            score += 0.14
        elif unknown_ratio >= 0.6:
            score -= 0.22
        if any(token in context.dynamic_stop_tokens or token in NOISE_TOKENS for token in tokens):
            score -= 0.28
        return max(0.0, min(1.0, round(score, 2)))

    def business_relevance_score(
        self,
        value: str,
        context: BusinessContextProfile,
        *,
        keep_product_terms: bool = False,
    ) -> float:
        keyword = self.normalize_query(value, context)
        tokens = [token for token in keyword.split() if token]
        if not tokens:
            return 0.0
        allowed_service_tokens = set(context.service_tokens)
        if keep_product_terms:
            allowed_service_tokens.update(context.commerce_tokens)
        service_overlap = len(set(tokens) & allowed_service_tokens)
        industry_overlap = len(set(tokens) & context.industry_tokens)
        location_overlap = len(set(tokens) & context.location_tokens)
        score = 0.0
        if service_overlap:
            score += min(0.55, service_overlap * 0.2)
        lexical_overlap = len(set(tokens) & (SERVICE_TOKENS | ECOMMERCE_TOKENS | context.industry_tokens))
        if lexical_overlap:
            score += min(0.25, lexical_overlap * 0.09)
        if industry_overlap:
            score += min(0.2, industry_overlap * 0.08)
        if location_overlap:
            score += 0.08
        if any(phrase in keyword for phrase in context.service_phrases[:12]):
            score += 0.2
        if self._is_question_like(keyword) and (service_overlap or industry_overlap):
            score += 0.08
        if self._unknown_token_ratio(tokens, context) >= 0.55:
            score -= 0.2
        return max(0.0, min(1.0, round(score, 2)))

    def hallucination_detected(self, value: str, context: BusinessContextProfile) -> bool:
        keyword = self.normalize_query(value, context)
        tokens = [token for token in keyword.split() if token]
        if not tokens:
            return True
        if any(token in NOISE_TOKENS or token in context.dynamic_stop_tokens for token in tokens):
            return True
        unknown_ratio = self._unknown_token_ratio(tokens, context)
        relevant_overlap = len((set(tokens) & context.service_tokens) | (set(tokens) & context.industry_tokens))
        return unknown_ratio >= 0.6 and relevant_overlap == 0

    def is_valid_query(
        self,
        value: str,
        context: BusinessContextProfile,
        *,
        keep_product_terms: bool = False,
    ) -> bool:
        keyword = self.normalize_query(value, context)
        tokens = [token for token in keyword.split() if token]
        if len(tokens) < 2:
            return False
        meaningful_count = len(
            [
                token
                for token in tokens
                if token not in GENERIC_STOP_TOKENS
                and token not in context.location_tokens
            ]
        )
        if meaningful_count > 6 and not self._is_question_like(keyword):
            return False
        if any(token in NOISE_TOKENS or token in context.dynamic_stop_tokens for token in tokens):
            return False
        if self._has_stacked_modifiers(tokens):
            return False
        if self._has_repeated_tokens(tokens):
            return False
        if self._looks_like_fragment(keyword, tokens):
            return False
        if self.hallucination_detected(keyword, context):
            return False
        if self.naturalness_score(keyword, context) < 0.62:
            return False
        if self.business_relevance_score(keyword, context, keep_product_terms=keep_product_terms) < 0.58:
            return False
        return True

    def root_phrase(
        self,
        value: str,
        context: BusinessContextProfile,
        *,
        keep_product_terms: bool = False,
    ) -> str:
        keyword = self.normalize_query(value, context)
        if not keyword:
            return ""
        best_match = ""
        best_score = 0.0
        for phrase in context.service_phrases:
            if not phrase or phrase not in keyword:
                continue
            if not self.is_valid_query(phrase, context, keep_product_terms=keep_product_terms):
                continue
            phrase_tokens = set(phrase.split())
            score = (
                self.business_relevance_score(phrase, context, keep_product_terms=keep_product_terms) * 0.65
                + self.naturalness_score(phrase, context) * 0.35
                - (0.08 * len(phrase_tokens & context.location_tokens))
                - (0.05 * len(phrase_tokens & COMMERCIAL_MODIFIER_TOKENS))
            )
            if score > best_score:
                best_match = phrase
                best_score = score
        if best_match:
            return best_match

        tokens = []
        allowed = set(context.service_tokens) | set(context.industry_tokens)
        if keep_product_terms:
            allowed |= set(context.commerce_tokens)
        for token in keyword.split():
            if token in QUESTION_TOKENS or token in COMMERCIAL_MODIFIER_TOKENS:
                continue
            if token in context.location_tokens or token in GENERIC_STOP_TOKENS:
                continue
            if token in context.brand_tokens or token in context.dynamic_stop_tokens:
                continue
            if token in allowed or token in ALLOWED_QUERY_TOKENS:
                tokens.append(token)
        candidate = re.sub(r"\s+", " ", " ".join(tokens)).strip()
        if self.is_valid_query(candidate, context, keep_product_terms=keep_product_terms):
            return candidate
        return ""

    def best_cluster_root(
        self,
        candidates: Iterable[str],
        context: BusinessContextProfile,
        *,
        keep_product_terms: bool = False,
    ) -> str:
        best_phrase = ""
        best_score = 0.0
        for candidate in candidates:
            root = self.root_phrase(candidate, context, keep_product_terms=keep_product_terms)
            if not root:
                continue
            score = (
                self.business_relevance_score(root, context, keep_product_terms=keep_product_terms) * 0.6
                + self.naturalness_score(root, context) * 0.4
            )
            if score > best_score:
                best_phrase = root
                best_score = score
        return best_phrase

    def _add_phrase(
        self,
        phrase_scores: dict[str, float],
        phrase: str,
        weight: float,
        brand_tokens: set[str],
        location_tokens: set[str],
    ) -> None:
        cleaned = self._normalize_phrase(phrase, brand_tokens, location_tokens)
        if not cleaned:
            return
        phrase_scores[cleaned] = max(phrase_scores.get(cleaned, 0.0), weight)

    def _add_phrase_parts(
        self,
        phrase_scores: dict[str, float],
        phrase: str,
        weight: float,
        brand_tokens: set[str],
        location_tokens: set[str],
    ) -> None:
        for part in re.split(r"[|,/:\-–]+", phrase):
            self._add_phrase(phrase_scores, part, weight, brand_tokens, location_tokens)

    def _phrases_from_url(self, value: str) -> list[str]:
        parsed = urlparse(value)
        parts = [part for part in parsed.path.lower().split("/") if part]
        if not parts:
            return []
        phrases: list[str] = []
        for size in (2, 1):
            phrase = " ".join(
                segment.replace("-", " ").replace("_", " ")
                for segment in parts[-size:]
            )
            phrases.append(phrase)
        return phrases

    def _phrases_from_excerpt(self, text: str) -> list[str]:
        if not text:
            return []
        cleaned = re.sub(r"\s+", " ", text.lower())
        chunks = re.split(r"[|,;:.()]+", cleaned)
        phrases: list[str] = []
        for chunk in chunks[:18]:
            words = [TOKEN_MAP.get(token, token) for token in self._tokenize(chunk)]
            if len(words) < 2:
                continue
            for start in range(0, max(1, len(words) - 1)):
                window = words[start : start + 4]
                if 2 <= len(window) <= 4:
                    phrases.append(" ".join(window))
        return phrases[:36]

    def _normalize_phrase(
        self,
        value: str,
        brand_tokens: set[str],
        location_tokens: set[str],
    ) -> str:
        tokens = [
            token
            for token in self._tokenize(value)
            if token not in brand_tokens
            and token not in NAVIGATION_TOKENS
            and token not in NOISE_TOKENS
        ]
        if len(tokens) < 2 or len(tokens) > 6:
            return ""
        if self._has_repeated_tokens(tokens):
            return ""
        filtered = [
            token
            for token in tokens
            if token not in GENERIC_STOP_TOKENS
            and token not in COMMERCIAL_MODIFIER_TOKENS
            and token not in QUESTION_TOKENS
            and token not in {"service", "services", "product", "products", "category", "categories", "collection", "collections"}
        ]
        if len(filtered) < 2:
            return ""
        if all(token in location_tokens for token in filtered):
            return ""
        return " ".join(filtered[:5])

    def _tokenize(self, value: str) -> list[str]:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())
        return [TOKEN_MAP.get(token, token) for token in cleaned.split() if token]

    def _token_set(self, value: str) -> set[str]:
        return {token for token in self._tokenize(value) if len(token) > 2}

    def _is_question_like(self, value: str) -> bool:
        return value.startswith(
            ("how ", "what ", "why ", "when ", "who ", "where ", "can ", "should ", "does ", "do ", "is ")
        )

    def _has_repeated_tokens(self, tokens: list[str]) -> bool:
        meaningful = [token for token in tokens if token not in GENERIC_STOP_TOKENS]
        if len(set(meaningful)) <= 1:
            return True
        return any(meaningful[index] == meaningful[index - 1] for index in range(1, len(meaningful)))

    def _has_stacked_modifiers(self, tokens: list[str]) -> bool:
        modifiers = [token for token in tokens if token in COMMERCIAL_MODIFIER_TOKENS]
        if len(modifiers) >= 2:
            return True
        if {"near", "me"} & set(tokens) and {"company", "specialist", "specialists"} & set(tokens):
            return True
        return False

    def _looks_like_fragment(self, keyword: str, tokens: list[str]) -> bool:
        fragment_tokens = {
            "essential",
            "role",
            "protecting",
            "homes",
            "benefits",
            "guide",
            "ultimate",
            "complete",
            "small",
            "professional",
            "offers",
        }
        if len(tokens) > 6 and not self._is_question_like(keyword):
            return True
        if sum(1 for token in tokens if token in fragment_tokens) >= 2:
            return True
        return False

    def _unknown_token_ratio(self, tokens: list[str], context: BusinessContextProfile) -> float:
        allowed = (
            set(context.service_tokens)
            | set(context.commerce_tokens)
            | set(context.industry_tokens)
            | set(context.location_tokens)
            | set(context.context_tokens)
            | set(context.brand_tokens)
            | ALLOWED_QUERY_TOKENS
            | GENERIC_STOP_TOKENS
            | QUESTION_TOKENS
            | COMMERCIAL_MODIFIER_TOKENS
        )
        meaningful = [token for token in tokens if token not in GENERIC_STOP_TOKENS]
        if not meaningful:
            return 1.0
        unknown = [token for token in meaningful if token not in allowed]
        return len(unknown) / max(len(meaningful), 1)
