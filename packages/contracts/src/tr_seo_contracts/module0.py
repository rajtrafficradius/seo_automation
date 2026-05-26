from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BusinessType(str, Enum):
    SERVICE = "service"
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    LOCAL = "local"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class KeywordPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class KeywordIntent(str, Enum):
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL_AEO = "navigational_aeo"
    INFORMATIONAL = "informational"


class RunMessageSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CDDFileMeta(BaseModel):
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    extension: str


class CDDExtraction(BaseModel):
    text_preview: str
    sections_detected: list[str] = Field(default_factory=list)
    parser_used: str
    detected_domains: list[str] = Field(default_factory=list)
    competitor_hints: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RunMessage(BaseModel):
    code: str
    severity: RunMessageSeverity
    message: str
    source: str


class RunTimestamps(BaseModel):
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    data_fresh_until: datetime | None = None


class RobotsTxtStatus(BaseModel):
    url: str
    fetched: bool = False
    status_code: int | None = Field(default=None, ge=100, le=599)
    allows_ai_crawlers: bool | None = None
    blocked_agents: list[str] = Field(default_factory=list)
    sitemap_directives: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SitemapStatus(BaseModel):
    discovered: bool = False
    sitemap_urls: list[str] = Field(default_factory=list)
    fetched_count: int = Field(default=0, ge=0)
    url_count: int = Field(default=0, ge=0)
    sample_urls: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UrlInventorySection(BaseModel):
    section: str
    url_count: int = Field(default=0, ge=0)


class UrlInventorySummary(BaseModel):
    total_urls: int = Field(default=0, ge=0)
    discovered_urls: list[str] = Field(default_factory=list)
    sample_urls: list[str] = Field(default_factory=list)
    top_sections: list[UrlInventorySection] = Field(default_factory=list)
    service_like_urls: list[str] = Field(default_factory=list)
    location_like_urls: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SiteClassification(BaseModel):
    business_type: BusinessType
    detected_domain: str
    industry_category: str = "general_business"
    geographic_target: str = "unverified_market_scope"
    language: str = "unverified"
    cms: str = "unknown"
    cms_version: str | None = None
    site_scale_tier: str = "unknown"
    page_builder: str | None = None
    sitemap_url: str | None = None
    active_components: list[str] = Field(default_factory=list)
    theme_or_template: str | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class WebsiteProfile(BaseModel):
    homepage_status_code: int | None = Field(default=None, ge=100, le=599)
    final_status_code: int | None = Field(default=None, ge=100, le=599)
    response_time_ms: int | None = Field(default=None, ge=0)
    redirect_count: int = Field(default=0, ge=0)
    homepage_title: str | None = None
    meta_description: str | None = None
    homepage_text_excerpt: str | None = None
    canonical_url: str | None = None
    word_count: int = Field(default=0, ge=0)
    h1_count: int = Field(default=0, ge=0)
    primary_schema_type: str | None = None
    mobile_friendly: bool | None = None
    broken_internal_links: list[str] = Field(default_factory=list)
    indexable: bool | None = None
    important_headers: dict[str, str] = Field(default_factory=dict)
    detected_schema_types: list[str] = Field(default_factory=list)
    social_profile_links: list[str] = Field(default_factory=list)
    sample_page_titles: list[str] = Field(default_factory=list)
    observed_headings: list[str] = Field(default_factory=list)
    navigation_labels: list[str] = Field(default_factory=list)
    service_terminology: list[str] = Field(default_factory=list)
    robots_txt: RobotsTxtStatus
    sitemap: SitemapStatus
    url_inventory: UrlInventorySummary


class CompetitorRecord(BaseModel):
    domain: str
    name: str
    source: str
    reason_for_selection: str = ""
    likely_services: list[str] = Field(default_factory=list)
    content_gaps: list[str] = Field(default_factory=list)
    service_gaps: list[str] = Field(default_factory=list)
    estimated_strength: int = Field(default=0, ge=0, le=100)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_estimated: bool = False
    anomaly_filtered: bool = False
    competition_level: float | None = Field(default=None, ge=0.0)
    shared_keywords: int | None = Field(default=None, ge=0)
    keyword_sample: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CompetitorGap(BaseModel):
    gap_type: str
    label: str
    supporting_keywords: list[str] = Field(default_factory=list)
    rationale: str
    opportunity_score: int = Field(default=0, ge=0, le=100)


class MinimumEffortPoint(BaseModel):
    proposed_url: str
    primary_keyword: str
    required_links: int = Field(default=0, ge=0)
    average_competitor_difficulty: int = Field(default=0, ge=0, le=100)
    monthly_link_velocity: int = Field(default=0, ge=0)
    notes: list[str] = Field(default_factory=list)


class KeywordCluster(BaseModel):
    cluster_id: str
    label: str
    intent: KeywordIntent
    primary_keyword: str
    keywords: list[str] = Field(default_factory=list)
    total_search_volume: int = Field(default=0, ge=0)
    suggested_url: str | None = None


class KeywordOpportunity(BaseModel):
    keyword: str
    cluster_id: str | None = None
    intent: KeywordIntent = KeywordIntent.INFORMATIONAL
    priority: KeywordPriority
    search_volume: int = Field(default=0, ge=0)
    keyword_difficulty: int = Field(default=0, ge=0, le=100)
    cpc: float | None = Field(default=None, ge=0.0)
    current_position: int | None = Field(default=None, ge=1)
    source: str = "semrush"
    mapped_url: str | None = None
    quick_win: bool = False
    ai_answer_trigger_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_estimated: bool = False
    notes: list[str] = Field(default_factory=list)


class QuickWinSummary(BaseModel):
    keywords: list[KeywordOpportunity] = Field(default_factory=list)
    total_count: int = Field(default=0, ge=0)


class UrlArchitectureItem(BaseModel):
    hierarchy_level: str
    page_type: str
    current_url: str | None = None
    proposed_url: str
    primary_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    search_volume: int = Field(default=0, ge=0)
    current_ranking: int | None = Field(default=None, ge=1)
    status: str = "new"
    priority: KeywordPriority = KeywordPriority.P2
    ai_answer_trigger_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    fan_out_coverage: float | None = Field(default=None, ge=0.0, le=1.0)


class TamDataset(BaseModel):
    total_monthly_search_volume: int = Field(default=0, ge=0)
    p1_p2_search_volume: int = Field(default=0, ge=0)
    current_capture_estimate: int = Field(default=0, ge=0)
    opportunity_gap: int = Field(default=0, ge=0)
    current_share_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    methodology: str


class AISOVQueryResult(BaseModel):
    engine: str = "hybrid_estimate"
    query: str
    keyword: str
    keyword_intent: KeywordIntent = KeywordIntent.INFORMATIONAL
    brand_likely_cited: bool = False
    cited: bool = False
    competitors_likely_cited: list[str] = Field(default_factory=list)
    competitor_cited: list[str] = Field(default_factory=list)
    citation_domains: list[str] = Field(default_factory=list)
    reason: str = ""
    citation_likelihood_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    content_gap: str = ""
    recommended_content_action: str = ""
    notes: list[str] = Field(default_factory=list)


class AISOVEngineResult(BaseModel):
    engine: str
    status: str
    target_queries: int = Field(default=0, ge=0)
    cited_queries: int = Field(default=0, ge=0)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class AISOVCompetitorVisibility(BaseModel):
    domain: str
    name: str = ""
    likely_visibility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_estimated: bool = True


class AISOVCitationLikelihood(BaseModel):
    keyword: str
    citation_likelihood_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class AISOVBaseline(BaseModel):
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_ai_sov_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = "not_configured"
    methodology: str
    brand_visibility_summary: str = ""
    competitor_visibility_comparison: list[AISOVCompetitorVisibility] = Field(default_factory=list)
    ai_answer_triggering_keywords: list[str] = Field(default_factory=list)
    missing_visibility_opportunities: list[str] = Field(default_factory=list)
    recommended_geo_aeo_actions: list[str] = Field(default_factory=list)
    citation_likelihood_by_keyword: list[AISOVCitationLikelihood] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    engine_results: list[AISOVEngineResult] = Field(default_factory=list)
    query_results: list[AISOVQueryResult] = Field(default_factory=list)
    missing_visibility_keywords: list[str] = Field(default_factory=list)


class FanOutSubQuery(BaseModel):
    query: str
    content_requirement: str
    has_content: bool = False
    source: str = "heuristic"


class FanOutKeywordMap(BaseModel):
    root_keyword: str
    sub_queries: list[FanOutSubQuery] = Field(default_factory=list)
    invisible_keywords: list[str] = Field(default_factory=list)
    coverage_score: float = Field(default=0.0, ge=0.0, le=1.0)


class FanOutMap(BaseModel):
    methodology: str
    average_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    keyword_maps: list[FanOutKeywordMap] = Field(default_factory=list)


class EntityMention(BaseModel):
    source_name: str
    source_url: str | None = None
    mention_type: str
    consistent: bool = True


class EntityAuthorityBaseline(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    knowledge_panel_status: str = "not_verified"
    same_as_links: list[str] = Field(default_factory=list)
    brand_mentions: list[EntityMention] = Field(default_factory=list)
    consistency_gaps: list[str] = Field(default_factory=list)
    reinforcement_opportunities: list[str] = Field(default_factory=list)
    methodology: str


class CompetitiveIntelligence(BaseModel):
    top_competitors: list[CompetitorRecord] = Field(default_factory=list)
    filtered_domains: list[str] = Field(default_factory=list)
    service_gaps: list[CompetitorGap] = Field(default_factory=list)
    content_gaps: list[CompetitorGap] = Field(default_factory=list)
    local_page_competitors: dict[str, list[str]] = Field(default_factory=dict)


class Module0ExportFile(BaseModel):
    filename: str
    content_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    download_url: str


class Module0Exports(BaseModel):
    cdd_extraction: Module0ExportFile | None = None
    site_classification: Module0ExportFile | None = None
    website_profile: Module0ExportFile | None = None
    semrush_snapshot: Module0ExportFile | None = None
    competitive_intelligence: Module0ExportFile | None = None
    keyword_universe: Module0ExportFile | None = None
    keyword_clusters: Module0ExportFile | None = None
    quick_wins: Module0ExportFile | None = None
    tam_dataset: Module0ExportFile | None = None
    url_architecture_map: Module0ExportFile | None = None
    minimum_effort_points: Module0ExportFile | None = None
    ai_sov_baseline: Module0ExportFile | None = None
    fan_out_map: Module0ExportFile | None = None
    entity_authority_baseline: Module0ExportFile | None = None
    warnings_errors: Module0ExportFile | None = None
    full_run_workbook: Module0ExportFile | None = None


class SEMrushSnapshot(BaseModel):
    configured: bool
    region_database: str = "us"
    status: str
    data_source: str = "unknown"
    fallback_used: bool = False
    is_estimated: bool = False
    warning_message: str | None = None
    keyword_limit: int | None = Field(default=None, ge=1)
    notes: list[str] = Field(default_factory=list)
    estimated_monthly_traffic: int | None = Field(default=None, ge=0)
    estimated_monthly_traffic_history: list[int] = Field(default_factory=list)
    organic_keyword_count: int | None = Field(default=None, ge=0)
    competitors_evaluated: int = Field(default=0, ge=0)
    source_file_name: str | None = None
    source_file_extension: str | None = None
    raw_keyword_rows: int | None = Field(default=None, ge=0)
    accepted_keyword_rows: int | None = Field(default=None, ge=0)
    rejected_keyword_rows: int | None = Field(default=None, ge=0)
    rejected_keyword_examples: list[str] = Field(default_factory=list)


class Module0Request(BaseModel):
    website_url: HttpUrl
    domain: str | None = None
    target_country: str = Field(min_length=2, max_length=3)
    brand_name: str = Field(min_length=1, max_length=200)
    business_type: BusinessType = BusinessType.UNKNOWN
    services_or_products: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    business_goals: list[str] = Field(default_factory=list)
    priority_services: list[str] = Field(default_factory=list)
    known_competitors: list[str] = Field(default_factory=list)
    excluded_services_or_pages: list[str] = Field(default_factory=list)
    brand_profiles: list[str] = Field(default_factory=list)
    notes: str | None = None


class Module0Response(BaseModel):
    request: Module0Request
    cdd_file: CDDFileMeta
    cdd_extraction: CDDExtraction
    site_classification: SiteClassification
    website_profile: WebsiteProfile
    semrush: SEMrushSnapshot
    competitive_intelligence: CompetitiveIntelligence
    master_keyword_universe: list[KeywordOpportunity] = Field(default_factory=list)
    keyword_universe_preview: list[KeywordOpportunity] = Field(default_factory=list)
    keyword_clusters: list[KeywordCluster] = Field(default_factory=list)
    quick_wins: QuickWinSummary
    tam_estimate: int = Field(default=0, ge=0)
    tam_dataset: TamDataset
    url_architecture_map: list[UrlArchitectureItem] = Field(default_factory=list)
    url_architecture_preview: list[UrlArchitectureItem] = Field(default_factory=list)
    minimum_effort_points: list[MinimumEffortPoint] = Field(default_factory=list)
    ai_sov_baseline: AISOVBaseline
    fan_out_map: FanOutMap
    entity_authority_baseline: EntityAuthorityBaseline
    exports: Module0Exports = Field(default_factory=Module0Exports)
    warnings_errors: list[RunMessage] = Field(default_factory=list)
    run_timestamps: RunTimestamps = Field(default_factory=RunTimestamps)
    next_steps: list[str] = Field(default_factory=list)
