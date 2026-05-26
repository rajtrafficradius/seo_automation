from __future__ import annotations

from tr_seo_contracts.module0 import (
    KeywordCluster,
    KeywordOpportunity,
    QuickWinSummary,
)
from tr_seo_module0.intent_classifier import IntentClassifier
from tr_seo_module0.keyword_clusterer import KeywordClusterer
from tr_seo_module0.semrush_client import SEMrushCompetitorRecord, SEMrushKeywordRecord


class KeywordEngine:
    def __init__(
        self,
        intent_classifier: IntentClassifier | None = None,
        clusterer: KeywordClusterer | None = None,
    ) -> None:
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.clusterer = clusterer or KeywordClusterer()

    def build_master_universe(
        self,
        semrush_keywords: list[SEMrushKeywordRecord],
        competitor_records: list[SEMrushCompetitorRecord],
        services_or_products: list[str],
        brand_name: str,
    ) -> tuple[list[KeywordOpportunity], list[KeywordCluster]]:
        if semrush_keywords:
            universe = self._build_from_semrush(
                semrush_keywords=semrush_keywords,
                competitor_records=competitor_records,
                brand_name=brand_name,
            )
        else:
            universe = self._build_seed_preview(
                services_or_products=services_or_products,
                brand_name=brand_name,
            )

        clusters = self.clusterer.cluster(universe)
        cluster_lookup = {cluster.cluster_id: cluster for cluster in clusters}
        for keyword in universe:
            if not keyword.mapped_url and keyword.cluster_id and keyword.cluster_id in cluster_lookup:
                keyword.mapped_url = cluster_lookup[keyword.cluster_id].suggested_url
        return universe, clusters

    def _build_seed_preview(
        self,
        services_or_products: list[str],
        brand_name: str,
    ) -> list[KeywordOpportunity]:
        brand_terms = {token for token in brand_name.lower().split() if token}
        keywords: list[KeywordOpportunity] = []
        seen: set[str] = set()
        seeds = []
        for service in services_or_products[:8]:
            normalized = service.strip()
            if not normalized:
                continue
            seeds.extend(
                [
                    normalized.lower(),
                    f"{brand_name} {normalized}".strip().lower(),
                    f"{normalized} service".strip().lower(),
                    f"{normalized} cost".strip().lower(),
                ]
            )

        for keyword in seeds:
            if keyword in seen:
                continue
            seen.add(keyword)
            intent, priority = self.intent_classifier.classify(keyword, brand_terms)
            keywords.append(
                KeywordOpportunity(
                    keyword=keyword,
                    intent=intent,
                    priority=priority,
                    search_volume=0,
                    keyword_difficulty=0,
                    current_position=None,
                    source="seeded-from-cdd",
                    quick_win=False,
                    ai_answer_trigger_rate=self._estimate_ai_trigger_rate(keyword, intent),
                    confidence_score=0.3,
                    quality_score=0.25,
                    is_estimated=True,
                )
            )
        return keywords[:40]

    def _build_from_semrush(
        self,
        semrush_keywords: list[SEMrushKeywordRecord],
        competitor_records: list[SEMrushCompetitorRecord],
        brand_name: str,
    ) -> list[KeywordOpportunity]:
        brand_terms = {token for token in brand_name.lower().split() if token}
        keywords: list[KeywordOpportunity] = []
        seen: set[str] = set()

        for item in semrush_keywords:
            normalized_keyword = item.keyword.strip().lower()
            if not normalized_keyword or normalized_keyword in seen:
                continue
            seen.add(normalized_keyword)
            intent, priority = self.intent_classifier.classify(normalized_keyword, brand_terms)
            quick_win = (
                priority.value == "P1"
                and item.keyword_difficulty <= 30
                and item.current_position is not None
                and 4 <= item.current_position <= 20
            )
            keywords.append(
                KeywordOpportunity(
                    keyword=normalized_keyword,
                    intent=intent,
                    priority=priority,
                    search_volume=item.search_volume,
                    keyword_difficulty=item.keyword_difficulty,
                    cpc=item.cpc,
                    current_position=item.current_position,
                    source=item.source,
                    mapped_url=item.mapped_url,
                    quick_win=quick_win,
                    ai_answer_trigger_rate=item.ai_answer_trigger_rate
                    if item.ai_answer_trigger_rate is not None
                    else self._estimate_ai_trigger_rate(normalized_keyword, intent),
                    confidence_score=item.confidence_score,
                    quality_score=item.quality_score,
                    is_estimated=item.is_estimated,
                    notes=list(item.notes),
                )
            )

        for competitor in competitor_records:
            for keyword in competitor.keyword_sample[:8]:
                normalized_keyword = keyword.strip().lower()
                if not normalized_keyword or normalized_keyword in seen:
                    continue
                seen.add(normalized_keyword)
                intent, priority = self.intent_classifier.classify(normalized_keyword, brand_terms)
                keywords.append(
                    KeywordOpportunity(
                        keyword=normalized_keyword,
                        intent=intent,
                        priority=priority,
                        search_volume=0,
                        keyword_difficulty=0,
                        cpc=None,
                        current_position=None,
                        source=f"competitor:{competitor.domain}",
                        quick_win=False,
                        ai_answer_trigger_rate=self._estimate_ai_trigger_rate(normalized_keyword, intent),
                        confidence_score=max(competitor.confidence_score, 0.4),
                        quality_score=0.45,
                        is_estimated=competitor.is_estimated,
                        notes=["Added from competitor keyword sample."],
                    )
                )

        keywords.sort(
            key=lambda item: (
                item.priority.value,
                -item.search_volume,
                item.current_position or 999,
                item.keyword,
            )
        )
        return keywords

    def quick_wins(self, keywords: list[KeywordOpportunity]) -> QuickWinSummary:
        quick_win_keywords = [keyword for keyword in keywords if keyword.quick_win]
        return QuickWinSummary(keywords=quick_win_keywords, total_count=len(quick_win_keywords))

    def _estimate_ai_trigger_rate(self, keyword: str, intent) -> float:
        lowered = keyword.lower()
        if any(token in lowered for token in ["what", "how", "why", "best", "cost", "price", "vs"]):
            return 0.75
        if intent.value == "navigational_aeo":
            return 0.55
        if intent.value == "transactional":
            return 0.45
        return 0.35
