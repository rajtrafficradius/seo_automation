from __future__ import annotations

import re
from urllib.parse import urlparse

from tr_seo_contracts.module0 import (
    BusinessType,
    SiteClassification,
    KeywordCluster,
    KeywordIntent,
    KeywordOpportunity,
    KeywordPriority,
    UrlArchitectureItem,
    WebsiteProfile,
)
from tr_seo_module0.business_context import BusinessContextAnalyzer


QUESTION_TOKENS = {
    "how",
    "what",
    "why",
    "when",
    "who",
    "where",
    "does",
    "do",
    "can",
    "should",
    "is",
    "are",
    "i",
}

COMMERCIAL_FILLER_TOKENS = {
    "cost",
    "costs",
    "quote",
    "quotes",
    "price",
    "prices",
    "pricing",
    "near",
    "me",
    "best",
    "cheap",
    "affordable",
    "reviews",
    "company",
    "specialist",
    "specialists",
    "professional",
    "professionals",
    "expert",
    "experts",
}

SERVICE_HINT_TOKENS = {
    "service",
    "services",
    "repair",
    "repairs",
    "replacement",
    "replace",
    "installation",
    "install",
    "maintenance",
    "fitout",
    "consulting",
}

ECOMMERCE_HINT_TOKENS = {
    "product",
    "products",
    "category",
    "categories",
    "collection",
    "collections",
    "shop",
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
    "seating",
    "storage",
}

ARCHITECTURE_NOISE_TOKENS = {
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


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


class UrlMapper:
    def __init__(self, context_analyzer: BusinessContextAnalyzer | None = None) -> None:
        self.context_analyzer = context_analyzer or BusinessContextAnalyzer()

    def build_map(
        self,
        business_type: BusinessType,
        brand_name: str,
        target_locations: list[str],
        clusters: list[KeywordCluster],
        existing_urls: list[str],
        keyword_universe: list[KeywordOpportunity] | None = None,
        services_or_products: list[str] | None = None,
        site_classification: SiteClassification | None = None,
        website_profile: WebsiteProfile | None = None,
    ) -> list[UrlArchitectureItem]:
        context = self.context_analyzer.build(
            site_classification=site_classification,
            website_profile=website_profile,
            business_type=business_type,
            brand_name=brand_name,
            target_locations=target_locations,
            services_or_products=services_or_products or [],
            existing_urls=existing_urls,
        )
        keyword_url_hints = self._keyword_url_hints(
            keyword_universe=keyword_universe or [],
            business_type=business_type,
            context=context,
        )
        homepage_keyword = self._homepage_keyword(
            brand_name=brand_name,
            business_type=business_type,
            target_locations=target_locations,
            service_candidates=[],
            commerce_candidates=[],
        )
        items: list[UrlArchitectureItem] = [
            UrlArchitectureItem(
                hierarchy_level="L1",
                page_type="homepage",
                current_url=self._find_homepage(existing_urls),
                proposed_url="/",
                primary_keyword=homepage_keyword,
                priority=KeywordPriority.P2,
            )
        ]

        service_candidates = self._service_candidates(
            clusters=clusters,
            brand_name=brand_name,
            target_locations=target_locations,
            context=context,
        )
        commerce_candidates = self._commerce_candidates(
            clusters=clusters,
            brand_name=brand_name,
            target_locations=target_locations,
            context=context,
        )

        if business_type == BusinessType.ECOMMERCE:
            items.extend(self._ecommerce_items(commerce_candidates, existing_urls, keyword_url_hints))
        elif business_type == BusinessType.HYBRID:
            items.extend(self._service_items(service_candidates[:5], existing_urls, target_locations, keyword_url_hints))
            items.extend(self._ecommerce_items(commerce_candidates[:5], existing_urls, keyword_url_hints))
        else:
            items.extend(self._service_items(service_candidates, existing_urls, target_locations, keyword_url_hints))

        if items:
            items[0].primary_keyword = self._homepage_keyword(
                brand_name=brand_name,
                business_type=business_type,
                target_locations=target_locations,
                service_candidates=service_candidates,
                commerce_candidates=commerce_candidates,
            )

        if target_locations and business_type in {
            BusinessType.SERVICE,
            BusinessType.LOCAL,
            BusinessType.HYBRID,
        }:
            items.extend(
                self._location_items(
                    service_candidates=service_candidates[:4],
                    target_locations=target_locations,
                    existing_urls=existing_urls,
                )
            )

        return self._dedupe_items(items)

    def _service_items(
        self,
        candidates: list[dict[str, object]],
        existing_urls: list[str],
        target_locations: list[str],
        keyword_url_hints: dict[str, str],
    ) -> list[UrlArchitectureItem]:
        items: list[UrlArchitectureItem] = []
        service_prefix = self._service_prefix(existing_urls, keyword_url_hints.values())
        parent_map = self._service_parent_map(candidates)
        location_slugs = {slugify(location) for location in target_locations if location.strip()}

        for candidate in candidates[:8]:
            keyword = str(candidate["primary_keyword"])
            slug = str(candidate["slug"])
            matched_url = keyword_url_hints.get(slug) or self._find_existing_by_slug(slug, existing_urls)
            parent_slug = parent_map.get(slug)
            proposed_url = self._service_candidate_url(
                slug=slug,
                parent_slug=parent_slug,
                matched_url=matched_url,
                service_prefix=service_prefix,
            )
            path_slug = proposed_url.strip("/").split("/")[-1] if proposed_url.strip("/") else ""
            if path_slug in location_slugs:
                continue

            items.append(
                UrlArchitectureItem(
                    hierarchy_level="L3" if parent_slug else "L2",
                    page_type="subservice" if parent_slug else "service",
                    current_url=matched_url,
                    proposed_url=proposed_url,
                    primary_keyword=keyword,
                    secondary_keywords=list(candidate["secondary_keywords"]),
                    search_volume=int(candidate["search_volume"]),
                    status="existing" if matched_url else "new",
                    priority=candidate["priority"],
                )
            )
        return items

    def _location_items(
        self,
        service_candidates: list[dict[str, object]],
        target_locations: list[str],
        existing_urls: list[str],
    ) -> list[UrlArchitectureItem]:
        items: list[UrlArchitectureItem] = []
        strategy = self._location_strategy(existing_urls)

        for candidate in service_candidates:
            keyword = str(candidate["primary_keyword"])
            slug = str(candidate["slug"])
            for location in target_locations[:3]:
                location_slug = slugify(location)
                if not location_slug or location_slug in slug:
                    continue

                matched_url = self._find_geo_existing(slug, location_slug, existing_urls)
                if matched_url:
                    proposed_url = self._path_from_url(matched_url)
                elif strategy == "locations_prefix":
                    proposed_url = f"/locations/{location_slug}/{slug}"
                else:
                    service_prefix = self._service_prefix(existing_urls, [])
                    if service_prefix:
                        proposed_url = f"{service_prefix}/{slug}/{location_slug}"
                    else:
                        proposed_url = f"/{slug}/{location_slug}"

                items.append(
                    UrlArchitectureItem(
                        hierarchy_level="L3",
                        page_type="geo",
                        current_url=matched_url,
                        proposed_url=proposed_url,
                        primary_keyword=f"{keyword} {location}".strip().lower(),
                        secondary_keywords=[keyword, location.lower()],
                        search_volume=int(candidate["search_volume"]),
                        status="existing" if matched_url else "new",
                        priority=KeywordPriority.P1,
                    )
                )
        return items

    def _ecommerce_items(
        self,
        candidates: list[dict[str, object]],
        existing_urls: list[str],
        keyword_url_hints: dict[str, str],
    ) -> list[UrlArchitectureItem]:
        items: list[UrlArchitectureItem] = []
        category_prefix = self._commerce_prefix(existing_urls)

        for candidate in candidates[:8]:
            keyword = str(candidate["primary_keyword"])
            slug = str(candidate["slug"])
            matched_url = keyword_url_hints.get(slug) or self._find_existing_by_slug(slug, existing_urls)
            proposed_url = self._path_from_url(matched_url) if matched_url else f"{category_prefix}/{slug}"
            items.append(
                UrlArchitectureItem(
                    hierarchy_level="L2",
                    page_type="category",
                    current_url=matched_url,
                    proposed_url=proposed_url,
                    primary_keyword=keyword,
                    secondary_keywords=list(candidate["secondary_keywords"]),
                    search_volume=int(candidate["search_volume"]),
                    status="existing" if matched_url else "new",
                    priority=candidate["priority"],
                )
            )
        return items

    def _service_candidates(
        self,
        clusters: list[KeywordCluster],
        brand_name: str,
        target_locations: list[str],
        context,
    ) -> list[dict[str, object]]:
        candidates: dict[str, dict[str, object]] = {}

        for cluster in clusters:
            root_keyword = self.context_analyzer.best_cluster_root(
                [cluster.primary_keyword, *cluster.keywords[:8]],
                context,
                keep_product_terms=False,
            )
            if not self._valid_architecture_keyword(root_keyword, context):
                continue

            if not self._looks_service_like(root_keyword, cluster):
                continue

            slug = slugify(root_keyword)
            entry = candidates.setdefault(
                slug,
                {
                    "slug": slug,
                    "primary_keyword": root_keyword,
                    "secondary_keywords": [],
                    "search_volume": 0,
                    "priority": KeywordPriority.P3,
                },
            )
            entry["search_volume"] = max(int(entry["search_volume"]), cluster.total_search_volume)
            entry["priority"] = self._higher_priority(entry["priority"], self._cluster_priority(cluster))
            for keyword in cluster.keywords[:6]:
                cleaned = self.context_analyzer.root_phrase(
                    keyword,
                    context,
                    keep_product_terms=False,
                )
                if (
                    cleaned
                    and cleaned != entry["primary_keyword"]
                    and cleaned not in entry["secondary_keywords"]
                    and self._valid_architecture_keyword(cleaned, context)
                ):
                    entry["secondary_keywords"].append(cleaned)

        return self._sort_candidates(candidates)

    def _commerce_candidates(
        self,
        clusters: list[KeywordCluster],
        brand_name: str,
        target_locations: list[str],
        context,
    ) -> list[dict[str, object]]:
        candidates: dict[str, dict[str, object]] = {}

        for cluster in clusters:
            root_keyword = self.context_analyzer.best_cluster_root(
                [cluster.primary_keyword, *cluster.keywords[:8]],
                context,
                keep_product_terms=True,
            )
            if not self._valid_architecture_keyword(root_keyword, context):
                continue

            if not self._looks_commerce_like(root_keyword, cluster):
                continue

            slug = slugify(root_keyword)
            entry = candidates.setdefault(
                slug,
                {
                    "slug": slug,
                    "primary_keyword": root_keyword,
                    "secondary_keywords": [],
                    "search_volume": 0,
                    "priority": KeywordPriority.P3,
                },
            )
            entry["search_volume"] = max(int(entry["search_volume"]), cluster.total_search_volume)
            entry["priority"] = self._higher_priority(entry["priority"], self._cluster_priority(cluster))
            for keyword in cluster.keywords[:6]:
                cleaned = self.context_analyzer.root_phrase(
                    keyword,
                    context,
                    keep_product_terms=True,
                )
                if (
                    cleaned
                    and cleaned != entry["primary_keyword"]
                    and cleaned not in entry["secondary_keywords"]
                    and self._valid_architecture_keyword(cleaned, context)
                ):
                    entry["secondary_keywords"].append(cleaned)

        return self._sort_candidates(candidates)

    def _valid_architecture_keyword(self, keyword: str, context) -> bool:
        tokens = [token for token in keyword.split() if token]
        if not tokens:
            return False
        if len(tokens) > 5:
            return False
        if any(token in ARCHITECTURE_NOISE_TOKENS for token in tokens):
            return False
        if keyword.startswith(("how ", "what ", "why ", "when ", "who ")):
            return False
        if any(tokens[index] == tokens[index - 1] for index in range(1, len(tokens))):
            return False
        if self.context_analyzer.hallucination_detected(keyword, context):
            return False
        if self.context_analyzer.naturalness_score(keyword, context) < 0.64:
            return False
        if self.context_analyzer.business_relevance_score(keyword, context, keep_product_terms=True) < 0.6:
            return False
        return True

    def _looks_question_like(self, keyword: str) -> bool:
        lowered = keyword.lower().strip()
        return lowered.startswith(("how ", "what ", "why ", "when ", "who ", "where ", "can ", "should "))

    def _looks_service_like(self, keyword: str, cluster: KeywordCluster) -> bool:
        lowered = keyword.lower()
        if any(token in lowered.split() for token in SERVICE_HINT_TOKENS):
            return True
        return cluster.intent in {KeywordIntent.TRANSACTIONAL, KeywordIntent.NAVIGATIONAL_AEO}

    def _looks_commerce_like(self, keyword: str, cluster: KeywordCluster) -> bool:
        lowered = keyword.lower()
        if any(token in lowered.split() for token in ECOMMERCE_HINT_TOKENS):
            return True
        return cluster.intent == KeywordIntent.TRANSACTIONAL and not any(
            token in lowered.split() for token in SERVICE_HINT_TOKENS
        )

    def _sort_candidates(self, candidates: dict[str, dict[str, object]]) -> list[dict[str, object]]:
        items = list(candidates.values())
        items.sort(
            key=lambda item: (
                0 if item["priority"] == KeywordPriority.P1 else 1 if item["priority"] == KeywordPriority.P2 else 2,
                -int(item["search_volume"]),
                str(item["primary_keyword"]),
            )
        )
        return items

    def _cluster_priority(self, cluster: KeywordCluster) -> KeywordPriority:
        return KeywordPriority.P1 if cluster.intent == KeywordIntent.TRANSACTIONAL else KeywordPriority.P2

    def _higher_priority(self, current: KeywordPriority, incoming: KeywordPriority) -> KeywordPriority:
        order = {KeywordPriority.P1: 0, KeywordPriority.P2: 1, KeywordPriority.P3: 2}
        return incoming if order[incoming] < order[current] else current

    def _service_prefix(self, existing_urls: list[str], hinted_urls) -> str:
        prefixed = 0
        root_level = 0
        for url in [*existing_urls, *list(hinted_urls)]:
            path = urlparse(url).path.lower()
            if not path or path in {"", "/"}:
                continue
            if self._is_root_service_path(path):
                root_level += 1
            elif "/services/" in path or path.startswith("/services"):
                prefixed += 1
        if root_level >= max(2, prefixed + 1):
            return ""
        return "/services"

    def _commerce_prefix(self, existing_urls: list[str]) -> str:
        for candidate in ["/collections", "/categories", "/products", "/shop"]:
            if any(candidate in urlparse(url).path.lower() for url in existing_urls):
                return candidate
        return "/collections"

    def _location_strategy(self, existing_urls: list[str]) -> str:
        if any("/locations/" in urlparse(url).path.lower() for url in existing_urls):
            return "locations_prefix"
        return "service_nested"

    def _find_existing_by_slug(self, slug: str, existing_urls: list[str]) -> str | None:
        normalized_slug = slug.lower().strip("/")
        for url in existing_urls:
            path = urlparse(url).path.lower().strip("/")
            segments = [segment for segment in path.split("/") if segment]
            if normalized_slug and normalized_slug in segments:
                return url
        for url in existing_urls:
            path = urlparse(url).path.lower().strip("/")
            if normalized_slug and path.endswith(normalized_slug):
                return url
        for url in existing_urls:
            path = urlparse(url).path.lower().strip("/")
            if normalized_slug and normalized_slug in path:
                return url
        return None

    def _find_geo_existing(self, service_slug: str, location_slug: str, existing_urls: list[str]) -> str | None:
        for url in existing_urls:
            path = urlparse(url).path.lower().strip("/")
            if service_slug in path and location_slug in path:
                return url
        return None

    def _find_homepage(self, existing_urls: list[str]) -> str | None:
        for url in existing_urls:
            parsed = urlparse(url)
            if parsed.path in {"", "/"}:
                return url
        return None

    def _path_from_url(self, url: str | None) -> str:
        if not url:
            return "/"
        path = urlparse(url).path or "/"
        return path.rstrip("/") or "/"

    def _dedupe_items(self, items: list[UrlArchitectureItem]) -> list[UrlArchitectureItem]:
        deduped: list[UrlArchitectureItem] = []
        seen_paths: set[str] = set()
        for item in items:
            path = item.proposed_url.rstrip("/") or "/"
            if path in seen_paths:
                continue
            seen_paths.add(path)
            deduped.append(item)
        return deduped

    def _service_candidate_url(
        self,
        *,
        slug: str,
        parent_slug: str | None,
        matched_url: str | None,
        service_prefix: str,
    ) -> str:
        if matched_url:
            return self._path_from_url(matched_url)
        if parent_slug:
            if service_prefix:
                return f"{service_prefix}/{parent_slug}/{slug}"
            return f"/{parent_slug}/{slug}"
        if service_prefix:
            return f"{service_prefix}/{slug}"
        return f"/{slug}"

    def _service_parent_map(self, candidates: list[dict[str, object]]) -> dict[str, str]:
        parent_map: dict[str, str] = {}
        for index, candidate in enumerate(candidates):
            child_slug = str(candidate["slug"])
            child_tokens = self._service_semantic_tokens(str(candidate["primary_keyword"]))
            if len(child_tokens) < 2:
                continue
            for possible_parent in candidates[:index]:
                parent_slug = str(possible_parent["slug"])
                parent_tokens = self._service_semantic_tokens(str(possible_parent["primary_keyword"]))
                if not parent_tokens or len(parent_tokens) >= len(child_tokens):
                    continue
                if not set(parent_tokens).issubset(set(child_tokens)):
                    continue
                if int(candidate["search_volume"]) > int(possible_parent["search_volume"]) * 1.2:
                    continue
                parent_map[child_slug] = parent_slug
                break
        return parent_map

    def _service_semantic_tokens(self, keyword: str) -> list[str]:
        ignored = {
            *COMMERCIAL_FILLER_TOKENS,
            *QUESTION_TOKENS,
            *SERVICE_HINT_TOKENS,
        }
        tokens = []
        for token in keyword.lower().split():
            if token in ignored or token in ARCHITECTURE_NOISE_TOKENS:
                continue
            if token in {"melbourne", "sydney", "brisbane", "perth", "adelaide", "richmond", "kew", "hawthorn"}:
                continue
            tokens.append(token)
        return list(dict.fromkeys(tokens))

    def _is_root_service_path(self, path: str) -> bool:
        normalized = path.strip("/")
        if not normalized or "/" in normalized:
            return False
        if normalized in ARCHITECTURE_NOISE_TOKENS or normalized in {"about", "contact", "gallery", "blog"}:
            return False
        return True

    def _keyword_url_hints(
        self,
        *,
        keyword_universe: list[KeywordOpportunity],
        business_type: BusinessType,
        context,
    ) -> dict[str, str]:
        hints: dict[str, str] = {}
        for keyword in keyword_universe:
            if not keyword.mapped_url:
                continue
            root = self.context_analyzer.root_phrase(
                keyword.keyword,
                context,
                keep_product_terms=business_type in {BusinessType.ECOMMERCE, BusinessType.HYBRID},
            )
            if not root or not self._valid_architecture_keyword(root, context):
                continue
            slug = slugify(root)
            hints.setdefault(slug, keyword.mapped_url)
        return hints

    def _homepage_keyword(
        self,
        *,
        brand_name: str,
        business_type: BusinessType,
        target_locations: list[str],
        service_candidates: list[dict[str, object]],
        commerce_candidates: list[dict[str, object]],
    ) -> str:
        if business_type in {BusinessType.ECOMMERCE} and commerce_candidates:
            primary = str(commerce_candidates[0]["primary_keyword"])
            return f"{brand_name.lower()} {primary}".strip()
        if service_candidates:
            primary = str(service_candidates[0]["primary_keyword"])
            location = target_locations[0].lower() if target_locations else ""
            if location and location not in primary:
                return f"{primary} {location}".strip()
            return primary
        return brand_name.lower()
