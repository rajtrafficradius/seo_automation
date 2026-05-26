from __future__ import annotations

from collections import defaultdict
import re

from tr_seo_contracts.module0 import (
    CompetitiveIntelligence,
    CompetitorGap,
    CompetitorRecord,
    KeywordOpportunity,
)
from tr_seo_module0.semrush_client import SEMrushCollectionResult, SEMrushCompetitorRecord


class CompetitorIntelligenceService:
    MARKETPLACE_ANOMALIES = {
        "amazon",
        "ebay",
        "wikipedia",
        "facebook",
        "linkedin",
        "youtube",
        "reddit",
        "pinterest",
    }

    def build(
        self,
        request_services: list[str],
        semrush_result: SEMrushCollectionResult,
        keyword_universe: list[KeywordOpportunity],
        url_map: list[str],
        known_competitors: list[str],
    ) -> CompetitiveIntelligence:
        filtered_domains: list[str] = []
        top_competitors: list[CompetitorRecord] = []

        raw_competitors = list(semrush_result.competitors)
        for competitor in known_competitors:
            raw_competitors.append(
                SEMrushCompetitorRecord(
                    domain=competitor,
                    competition_level=None,
                    shared_keywords=None,
                    keyword_sample=[],
                    source="frontend_known_competitor",
                )
            )

        seen: set[str] = set()
        for competitor in raw_competitors:
            domain = competitor.domain.lower().strip()
            if not domain or domain in seen:
                continue
            seen.add(domain)

            anomaly = any(token in domain for token in self.MARKETPLACE_ANOMALIES)
            if anomaly:
                filtered_domains.append(domain)

            likely_services = list(competitor.likely_services) or self._infer_likely_services(
                request_services=request_services,
                keyword_sample=competitor.keyword_sample,
            )
            service_gap_labels = list(competitor.service_gaps) or self._infer_service_gap_labels(
                request_services=request_services,
                keyword_sample=competitor.keyword_sample,
            )
            content_gap_labels = list(competitor.content_gaps) or self._infer_content_gap_labels(
                keyword_sample=competitor.keyword_sample,
                url_blob=" ".join(url_map).lower(),
            )
            top_competitors.append(
                CompetitorRecord(
                    domain=domain,
                    name=competitor.name or domain,
                    source=competitor.source,
                    reason_for_selection=competitor.reason_for_selection or self._reason_for_selection(
                        competitor_domain=domain,
                        shared_keywords=competitor.shared_keywords,
                        source=competitor.source,
                    ),
                    likely_services=likely_services,
                    content_gaps=content_gap_labels,
                    service_gaps=service_gap_labels,
                    estimated_strength=competitor.estimated_strength or self._estimate_strength(
                        competitor.shared_keywords,
                        competitor.keyword_sample,
                    ),
                    confidence_score=max(competitor.confidence_score, 0.55 if not anomaly else 0.35),
                    is_estimated=competitor.is_estimated,
                    anomaly_filtered=anomaly,
                    competition_level=competitor.competition_level,
                    shared_keywords=competitor.shared_keywords,
                    keyword_sample=competitor.keyword_sample[:12],
                    notes=(
                        ["Marketplace anomaly filtered from strategy-critical analysis."]
                        if anomaly
                        else []
                    )
                    + list(competitor.notes)
                    + self._build_competitor_notes(likely_services, service_gap_labels, content_gap_labels),
                )
            )

        client_keywords = {item.keyword for item in keyword_universe}
        url_blob = " ".join(url_map).lower()
        service_gaps: list[CompetitorGap] = []
        content_gaps: list[CompetitorGap] = []
        competitor_topic_buckets: dict[str, list[str]] = defaultdict(list)

        for competitor in top_competitors:
            if competitor.anomaly_filtered:
                continue
            for keyword in competitor.keyword_sample:
                competitor_topic_buckets[competitor.domain].append(keyword)
                if keyword not in client_keywords and any(service.lower() not in url_blob for service in request_services):
                    content_gaps.append(
                        CompetitorGap(
                            gap_type="content_gap",
                            label=keyword,
                            supporting_keywords=[keyword],
                            rationale=f"{competitor.domain} ranks for a keyword not present in the current client universe.",
                            opportunity_score=65,
                        )
                    )

        for service in request_services:
            normalized = service.lower().strip()
            if normalized and normalized not in url_blob:
                supporting = [
                    keyword
                    for competitor in top_competitors
                    for keyword in competitor.keyword_sample
                    if normalized.split()[0] in keyword
                ][:5]
                service_gaps.append(
                    CompetitorGap(
                        gap_type="service_gap",
                        label=service,
                        supporting_keywords=supporting,
                        rationale="Requested service is not clearly represented in the discovered URL inventory.",
                        opportunity_score=75,
                    )
                )

        if not service_gaps:
            for service in request_services[:3]:
                supporting = [
                    keyword.keyword for keyword in keyword_universe if any(token in keyword.keyword for token in service.lower().split()[:2])
                ][:5]
                service_gaps.append(
                    CompetitorGap(
                        gap_type="service_gap",
                        label=service,
                        supporting_keywords=supporting,
                        rationale="Strategic service gap inferred from onboarding priorities and the current URL architecture.",
                        opportunity_score=68,
                    )
                )

        if not content_gaps:
            priority_keywords = [
                keyword.keyword
                for keyword in keyword_universe
                if keyword.priority.value in {"P1", "P2"} and keyword.intent.value != "navigational_aeo"
            ][:6]
            for keyword in priority_keywords[:4]:
                content_gaps.append(
                    CompetitorGap(
                        gap_type="content_gap",
                        label=keyword,
                        supporting_keywords=[keyword],
                        rationale="Priority keyword needs a stronger dedicated page or section to improve competitive coverage.",
                        opportunity_score=62,
                    )
                )

        local_page_competitors = {
            url: [item.domain for item in top_competitors if not item.anomaly_filtered][:5]
            for url in url_map[:8]
        }
        if not local_page_competitors:
            local_page_competitors = {
                "/": [item.domain for item in top_competitors if not item.anomaly_filtered][:5]
            }

        return CompetitiveIntelligence(
            top_competitors=top_competitors[:10],
            filtered_domains=filtered_domains,
            service_gaps=service_gaps[:15],
            content_gaps=content_gaps[:25],
            local_page_competitors=local_page_competitors,
        )

    def _infer_likely_services(self, request_services: list[str], keyword_sample: list[str]) -> list[str]:
        matched: list[str] = []
        sample_blob = " ".join(keyword_sample).lower()
        for service in request_services:
            service_clean = service.strip()
            if not service_clean:
                continue
            service_tokens = [token for token in re.split(r"\W+", service_clean.lower()) if token]
            if any(token in sample_blob for token in service_tokens[:2]):
                matched.append(service_clean)
        if matched:
            return matched[:5]
        return request_services[:3] or ["Core commercial service coverage inferred from niche context"]

    def _infer_service_gap_labels(self, request_services: list[str], keyword_sample: list[str]) -> list[str]:
        sample_blob = " ".join(keyword_sample).lower()
        gaps = []
        for service in request_services:
            service_clean = service.strip()
            if not service_clean:
                continue
            if service_clean.lower() not in sample_blob:
                gaps.append(f"Limited visible competitor coverage for {service_clean.lower()}")
        return gaps[:4]

    def _infer_content_gap_labels(self, keyword_sample: list[str], url_blob: str) -> list[str]:
        gaps = []
        for keyword in keyword_sample[:8]:
            normalized = keyword.lower().strip()
            if not normalized or normalized in url_blob:
                continue
            gaps.append(f"No strong client page signal for {normalized}")
        return gaps[:4]

    def _reason_for_selection(self, competitor_domain: str, shared_keywords: int | None, source: str) -> str:
        if shared_keywords:
            return f"{competitor_domain} overlaps on approximately {shared_keywords} tracked keyword themes."
        if source.startswith("frontend") or source.startswith("cdd"):
            return f"{competitor_domain} was supplied as a relevant market competitor from project inputs."
        return f"{competitor_domain} appears strategically relevant within the same market and intent space."

    def _estimate_strength(self, shared_keywords: int | None, keyword_sample: list[str]) -> int:
        sample_score = min(len(keyword_sample) * 6, 40)
        overlap_score = min((shared_keywords or 0), 40)
        return max(35, min(100, 30 + sample_score + overlap_score))

    def _build_competitor_notes(
        self,
        likely_services: list[str],
        service_gaps: list[str],
        content_gaps: list[str],
    ) -> list[str]:
        notes: list[str] = []
        if likely_services:
            notes.append(f"Likely competing service themes: {', '.join(likely_services[:3])}.")
        if service_gaps:
            notes.append(f"Observed service gap pressure: {service_gaps[0]}.")
        if content_gaps:
            notes.append(f"Observed content gap pressure: {content_gaps[0]}.")
        return notes
