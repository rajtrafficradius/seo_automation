from __future__ import annotations

from datetime import timedelta

from tr_seo_contracts.module0 import (
    CDDFileMeta,
    CompetitiveIntelligence,
    MinimumEffortPoint,
    Module0Request,
    Module0Response,
    QuickWinSummary,
    RunMessage,
    RunMessageSeverity,
    RunTimestamps,
    TamDataset,
    utc_now,
)

from tr_seo_module0.ai_sov import AISOVService
from tr_seo_module0.cdd_parser import CDDParser
from tr_seo_module0.competitor_intelligence import CompetitorIntelligenceService
from tr_seo_module0.entity_authority import EntityAuthorityService
from tr_seo_module0.fanout_mapper import FanOutMapper
from tr_seo_module0.keyword_engine import KeywordEngine
from tr_seo_module0.semrush_client import SEMrushClient
from tr_seo_module0.site_inspector import SiteInspector
from tr_seo_module0.url_mapper import UrlMapper


class Module0Service:
    def __init__(
        self,
        cdd_parser: CDDParser | None = None,
        site_inspector: SiteInspector | None = None,
        semrush_client: SEMrushClient | None = None,
        keyword_engine: KeywordEngine | None = None,
        url_mapper: UrlMapper | None = None,
        competitor_intelligence_service: CompetitorIntelligenceService | None = None,
        ai_sov_service: AISOVService | None = None,
        fanout_mapper: FanOutMapper | None = None,
        entity_authority_service: EntityAuthorityService | None = None,
    ) -> None:
        self.cdd_parser = cdd_parser or CDDParser()
        self.site_inspector = site_inspector or SiteInspector()
        self.semrush_client = semrush_client or SEMrushClient()
        self.keyword_engine = keyword_engine or KeywordEngine()
        self.url_mapper = url_mapper or UrlMapper()
        self.competitor_intelligence_service = (
            competitor_intelligence_service or CompetitorIntelligenceService()
        )
        self.ai_sov_service = ai_sov_service or AISOVService()
        self.fanout_mapper = fanout_mapper or FanOutMapper()
        self.entity_authority_service = entity_authority_service or EntityAuthorityService()

    def run(self, request: Module0Request, cdd_meta: CDDFileMeta, cdd_content: bytes) -> Module0Response:
        return self.run_with_optional_keyword_upload(
            request=request,
            cdd_meta=cdd_meta,
            cdd_content=cdd_content,
            keyword_file_meta=None,
            keyword_file_content=None,
        )

    def run_with_optional_keyword_upload(
        self,
        *,
        request: Module0Request,
        cdd_meta: CDDFileMeta,
        cdd_content: bytes,
        keyword_file_meta: CDDFileMeta | None,
        keyword_file_content: bytes | None,
    ) -> Module0Response:
        started_at = utc_now()

        cdd_extraction = self.cdd_parser.parse(cdd_meta, cdd_content)
        site_classification, website_profile = self.site_inspector.inspect(request)
        semrush_result = self.semrush_client.collect(
            request,
            cdd_extraction=cdd_extraction,
            site_classification=site_classification,
            website_profile=website_profile,
            manual_keyword_file_meta=keyword_file_meta,
            manual_keyword_content=keyword_file_content,
        )
        keyword_universe, keyword_clusters = self.keyword_engine.build_master_universe(
            semrush_keywords=semrush_result.keywords,
            competitor_records=semrush_result.competitors,
            services_or_products=request.services_or_products,
            brand_name=request.brand_name,
        )
        url_architecture = self.url_mapper.build_map(
            business_type=site_classification.business_type,
            brand_name=request.brand_name,
            target_locations=request.target_locations,
            clusters=keyword_clusters,
            existing_urls=website_profile.url_inventory.discovered_urls,
            keyword_universe=keyword_universe,
            services_or_products=[*request.services_or_products, *request.priority_services],
            site_classification=site_classification,
            website_profile=website_profile,
        )
        self._apply_keyword_url_mapping(keyword_universe, keyword_clusters)
        quick_wins = self.keyword_engine.quick_wins(keyword_universe)
        tam_dataset = self._build_tam_dataset(keyword_universe, semrush_result.snapshot.estimated_monthly_traffic or 0)
        fan_out_map = self.fanout_mapper.build(
            keywords=[item for item in keyword_universe if item.priority.value in {"P1", "P2"}],
            existing_urls=website_profile.url_inventory.discovered_urls,
            target_locations=request.target_locations,
        )
        self._apply_url_metrics(url_architecture, keyword_universe, fan_out_map)
        competitive_intelligence = self.competitor_intelligence_service.build(
            request_services=request.services_or_products,
            semrush_result=semrush_result,
            keyword_universe=keyword_universe,
            url_map=[item.proposed_url for item in url_architecture],
            known_competitors=request.known_competitors,
        )
        minimum_effort_points = self._build_minimum_effort_points(
            url_architecture=url_architecture,
            keyword_universe=keyword_universe,
            competitive_intelligence=competitive_intelligence,
        )
        entity_authority = self.entity_authority_service.build(
            brand_name=request.brand_name,
            brand_profiles=request.brand_profiles,
            social_profile_links=website_profile.social_profile_links,
            detected_schema_types=website_profile.detected_schema_types,
        )
        ai_sov_baseline = self.ai_sov_service.build(
            keywords=[item for item in keyword_universe if item.priority.value in {"P1", "P2"}],
            brand_name=request.brand_name,
            request=request,
            website_profile=website_profile,
            competitors=competitive_intelligence.top_competitors,
            fan_out_map=fan_out_map,
            entity_authority_baseline=entity_authority,
        )
        warnings_errors = self._build_messages(
            cdd_extraction=cdd_extraction,
            site_classification=site_classification,
            website_profile=website_profile,
            semrush_warning=semrush_result.snapshot.warning_message,
            ai_sov_status=ai_sov_baseline.status,
        )

        next_steps = [
            "Module 1 should validate completeness, freshness, and URL-to-keyword mapping integrity before audit.",
            "Provider-backed AI SOV probing should replace heuristic AI visibility baselines before production rollout.",
        ]
        if semrush_result.snapshot.fallback_used:
            next_steps.insert(
                0,
                "Restore SEMrush credits or API access to automatically resume live data collection.",
            )

        completed_at = utc_now()
        return Module0Response(
            request=request,
            cdd_file=cdd_meta,
            cdd_extraction=cdd_extraction,
            site_classification=site_classification,
            website_profile=website_profile,
            semrush=semrush_result.snapshot,
            competitive_intelligence=competitive_intelligence,
            master_keyword_universe=keyword_universe,
            keyword_universe_preview=keyword_universe[:200],
            keyword_clusters=keyword_clusters,
            quick_wins=quick_wins,
            tam_estimate=tam_dataset.total_monthly_search_volume,
            tam_dataset=tam_dataset,
            url_architecture_map=url_architecture,
            url_architecture_preview=url_architecture[:50],
            minimum_effort_points=minimum_effort_points,
            ai_sov_baseline=ai_sov_baseline,
            fan_out_map=fan_out_map,
            entity_authority_baseline=entity_authority,
            warnings_errors=warnings_errors,
            run_timestamps=RunTimestamps(
                started_at=started_at,
                completed_at=completed_at,
                data_fresh_until=completed_at + timedelta(days=7),
            ),
            next_steps=next_steps,
        )

    def _build_messages(
        self,
        cdd_extraction,
        site_classification,
        website_profile,
        semrush_warning: str | None,
        ai_sov_status: str,
    ) -> list[RunMessage]:
        messages: list[RunMessage] = []
        for warning in cdd_extraction.warnings:
            messages.append(
                RunMessage(
                    code="cdd_warning",
                    severity=RunMessageSeverity.WARNING,
                    message=warning,
                    source="cdd_parser",
                )
            )
        if website_profile.robots_txt.fetched is False:
            messages.append(
                RunMessage(
                    code="robots_unavailable",
                    severity=RunMessageSeverity.WARNING,
                    message="robots.txt could not be confirmed during site inspection.",
                    source="site_inspector",
                )
            )
        if website_profile.sitemap.discovered is False:
            messages.append(
                RunMessage(
                    code="sitemap_unavailable",
                    severity=RunMessageSeverity.WARNING,
                    message="No sitemap was confirmed, so URL inventory depth may be limited.",
                    source="site_inspector",
                )
            )
        if site_classification.cms == "unknown":
            messages.append(
                RunMessage(
                    code="cms_unknown",
                    severity=RunMessageSeverity.INFO,
                    message="CMS/platform could not be confidently identified from the fetched site signals.",
                    source="site_inspector",
                )
            )
        if semrush_warning:
            messages.append(
                RunMessage(
                    code="semrush_fallback",
                    severity=RunMessageSeverity.WARNING,
                    message=semrush_warning,
                    source="semrush_client",
                )
            )
        if ai_sov_status != "live":
            messages.append(
                RunMessage(
                    code="ai_sov_not_live",
                    severity=RunMessageSeverity.WARNING,
                    message="AI Share of Voice is not yet provider-backed in this backend run.",
                    source="ai_sov",
                )
            )
        return messages

    def _apply_keyword_url_mapping(self, keywords, keyword_clusters) -> None:
        cluster_to_url = {
            cluster.cluster_id: cluster.suggested_url
            for cluster in keyword_clusters
            if cluster.suggested_url
        }
        for keyword in keywords:
            if not keyword.mapped_url and keyword.cluster_id and keyword.cluster_id in cluster_to_url:
                keyword.mapped_url = cluster_to_url[keyword.cluster_id]

    def _build_tam_dataset(
        self,
        keyword_universe,
        current_traffic: int,
    ) -> TamDataset:
        p1_p2_keywords = [item for item in keyword_universe if item.priority.value in {"P1", "P2"}]
        total_volume = sum(item.search_volume for item in keyword_universe)
        p1_p2_volume = sum(item.search_volume for item in p1_p2_keywords)
        opportunity_gap = max(p1_p2_volume - current_traffic, 0)
        share_ratio = (current_traffic / p1_p2_volume) if p1_p2_volume else 0.0
        return TamDataset(
            total_monthly_search_volume=total_volume,
            p1_p2_search_volume=p1_p2_volume,
            current_capture_estimate=current_traffic,
            opportunity_gap=opportunity_gap,
            current_share_ratio=min(share_ratio, 1.0),
            methodology="TAM = sum of all discovered keyword demand; strategic TAM focus = P1 + P2 demand; current capture estimated from SEMrush traffic baseline.",
        )

    def _apply_url_metrics(self, url_architecture, keyword_universe, fan_out_map) -> None:
        fanout_lookup = {item.root_keyword: item.coverage_score for item in fan_out_map.keyword_maps}
        for item in url_architecture:
            matches = [
                keyword
                for keyword in keyword_universe
                if keyword.mapped_url == item.proposed_url or keyword.keyword == item.primary_keyword
            ]
            if matches:
                item.search_volume = sum(keyword.search_volume for keyword in matches)
                rankings = [keyword.current_position for keyword in matches if keyword.current_position is not None]
                if rankings:
                    item.current_ranking = min(rankings)
                ai_rates = [keyword.ai_answer_trigger_rate for keyword in matches if keyword.ai_answer_trigger_rate is not None]
                if ai_rates:
                    item.ai_answer_trigger_rate = sum(ai_rates) / len(ai_rates)
            if item.primary_keyword in fanout_lookup:
                item.fan_out_coverage = fanout_lookup[item.primary_keyword]

    def _build_minimum_effort_points(
        self,
        url_architecture,
        keyword_universe,
        competitive_intelligence: CompetitiveIntelligence,
    ) -> list[MinimumEffortPoint]:
        competitor_count = max(
            1,
            len([item for item in competitive_intelligence.top_competitors if not item.anomaly_filtered]),
        )
        points: list[MinimumEffortPoint] = []

        for item in url_architecture[:20]:
            matching_keywords = [
                keyword
                for keyword in keyword_universe
                if keyword.mapped_url == item.proposed_url or keyword.keyword == item.primary_keyword
            ]
            if matching_keywords:
                avg_difficulty = int(
                    sum(keyword.keyword_difficulty for keyword in matching_keywords) / len(matching_keywords)
                )
            else:
                avg_difficulty = 20
            required_links = max(2, int(avg_difficulty / 10) + competitor_count)
            monthly_velocity = max(1, required_links // 3)
            points.append(
                MinimumEffortPoint(
                    proposed_url=item.proposed_url,
                    primary_keyword=item.primary_keyword,
                    required_links=required_links,
                    average_competitor_difficulty=avg_difficulty,
                    monthly_link_velocity=monthly_velocity,
                    notes=[
                        "Heuristic off-page baseline derived from competitor count and average keyword difficulty.",
                    ],
                )
            )
        return points
