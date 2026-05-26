from __future__ import annotations

from tr_seo_contracts.module0 import FanOutKeywordMap, FanOutMap, FanOutSubQuery, KeywordOpportunity


class FanOutMapper:
    def build(
        self,
        keywords: list[KeywordOpportunity],
        existing_urls: list[str],
        target_locations: list[str],
        max_keywords: int = 20,
    ) -> FanOutMap:
        maps: list[FanOutKeywordMap] = []
        normalized_urls = " ".join(existing_urls).lower()
        keyword_terms = {row.keyword for row in keywords}

        for keyword in keywords[:max_keywords]:
            sub_queries = self._sub_queries(keyword.keyword, target_locations)
            mapped = [
                FanOutSubQuery(
                    query=query,
                    content_requirement=self._content_requirement(query, keyword.keyword),
                    has_content=self._has_content(query, normalized_urls),
                )
                for query in sub_queries
            ]
            covered = [item for item in mapped if item.has_content]
            invisible = [item.query for item in mapped if item.query not in keyword_terms]
            maps.append(
                FanOutKeywordMap(
                    root_keyword=keyword.keyword,
                    sub_queries=mapped,
                    invisible_keywords=invisible,
                    coverage_score=(len(covered) / len(mapped)) if mapped else 0.0,
                )
            )

        average_coverage = (
            sum(item.coverage_score for item in maps) / len(maps)
            if maps
            else 0.0
        )
        return FanOutMap(
            methodology="Heuristic fan-out mapping using commercial query templates and existing URL coverage checks.",
            average_coverage=average_coverage,
            keyword_maps=maps,
        )

    def _sub_queries(self, keyword: str, target_locations: list[str]) -> list[str]:
        base = keyword.lower().strip()
        location = target_locations[0].lower() if target_locations else ""
        variants = [f"{base} cost", f"{base} service areas", f"{base} turnaround time"]
        if "repair" in base or "replacement" in base or "installation" in base:
            variants.extend(
                [
                    f"{base} process",
                    f"{base} materials",
                    f"{base} warranty",
                ]
            )
        else:
            variants.extend(
                [
                    f"best {base}",
                    f"{base} options",
                    f"{base} buyer guide",
                ]
            )
        if location:
            variants.extend(
                [
                    f"{base} {location}",
                    f"{base} {location} cost",
                    f"{base} {location} availability",
                ]
            )
        if not base.startswith(("how ", "what ", "why ")):
            variants.append(f"how much does {base} cost")
        seen: list[str] = []
        for variant in variants:
            if variant not in seen and len(variant.split()) <= 7:
                seen.append(variant)
        return seen

    def _content_requirement(self, query: str, root_keyword: str) -> str:
        if query.startswith("how "):
            return f"Add an FAQ or AEO block that directly answers '{query}' and links back to the core {root_keyword} page."
        if "cost" in query:
            return f"Create a pricing/commercial-intent section for '{query}' with qualification factors and next steps."
        if "service areas" in query or "availability" in query:
            return f"Add a service-area or coverage section targeting '{query}' with local proof points."
        if "process" in query or "materials" in query or "warranty" in query:
            return f"Create a support section explaining {query} to strengthen conversion and AI citation readiness."
        return f"Create or enrich a focused section answering '{query}' with clear internal links and schema-ready formatting."

    def _has_content(self, query: str, normalized_urls: str) -> bool:
        query_slug = query.replace(" ", "-")
        short_slug = "-".join(query.split()[:4])
        return query_slug in normalized_urls or short_slug in normalized_urls
