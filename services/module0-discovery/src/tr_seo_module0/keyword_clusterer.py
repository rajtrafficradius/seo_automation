from __future__ import annotations

import re
from collections import defaultdict

from tr_seo_contracts.module0 import KeywordCluster, KeywordIntent, KeywordOpportunity


class KeywordClusterer:
    STOPWORDS = {
        "best",
        "near",
        "me",
        "cost",
        "quote",
        "price",
        "prices",
        "service",
        "services",
        "company",
        "reviews",
        "how",
        "to",
        "in",
        "for",
        "the",
        "a",
        "an",
    }

    def cluster(self, keywords: list[KeywordOpportunity]) -> list[KeywordCluster]:
        groups: dict[str, list[KeywordOpportunity]] = defaultdict(list)
        for keyword in keywords:
            cluster_id = self._cluster_id(keyword.keyword)
            keyword.cluster_id = cluster_id
            groups[cluster_id].append(keyword)

        clusters: list[KeywordCluster] = []
        for cluster_id, items in groups.items():
            items.sort(key=lambda item: (item.priority.value, -item.search_volume, item.keyword))
            primary = items[0]
            total_volume = sum(item.search_volume for item in items)
            intent = self._dominant_intent(items)
            clusters.append(
                KeywordCluster(
                    cluster_id=cluster_id,
                    label=primary.keyword,
                    intent=intent,
                    primary_keyword=primary.keyword,
                    keywords=[item.keyword for item in items],
                    total_search_volume=total_volume,
                )
            )

        clusters.sort(key=lambda item: (-item.total_search_volume, item.label))
        return clusters

    def _cluster_id(self, keyword: str) -> str:
        normalized = re.sub(r"[^a-z0-9\s]", " ", keyword.lower())
        tokens = [token for token in normalized.split() if token not in self.STOPWORDS]
        if not tokens:
            tokens = normalized.split()
        return "-".join(tokens[:3]) or "general"

    def _dominant_intent(self, items: list[KeywordOpportunity]) -> KeywordIntent:
        counts: dict[KeywordIntent, int] = defaultdict(int)
        for item in items:
            counts[item.intent] += 1
        return max(counts, key=counts.get, default=KeywordIntent.INFORMATIONAL)
