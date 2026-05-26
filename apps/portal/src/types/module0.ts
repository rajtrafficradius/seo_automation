export type Module0FormValues = {
  websiteUrl: string;
  domain: string;
  targetCountry: string;
  brandName: string;
  businessType: string;
  servicesOrProducts: string;
  targetLocations: string;
  businessGoals: string;
  priorityServices: string;
  knownCompetitors: string;
  excludedServicesOrPages: string;
  brandProfiles: string;
  notes: string;
};

export type Module0ExportFile = {
  filename: string;
  content_type: string;
  download_url: string;
};

export type Module0Exports = {
  cdd_extraction?: Module0ExportFile | null;
  site_classification?: Module0ExportFile | null;
  website_profile?: Module0ExportFile | null;
  semrush_snapshot?: Module0ExportFile | null;
  competitive_intelligence?: Module0ExportFile | null;
  keyword_universe?: Module0ExportFile | null;
  keyword_clusters?: Module0ExportFile | null;
  quick_wins?: Module0ExportFile | null;
  tam_dataset?: Module0ExportFile | null;
  url_architecture_map?: Module0ExportFile | null;
  minimum_effort_points?: Module0ExportFile | null;
  ai_sov_baseline?: Module0ExportFile | null;
  fan_out_map?: Module0ExportFile | null;
  entity_authority_baseline?: Module0ExportFile | null;
  warnings_errors?: Module0ExportFile | null;
  full_run_workbook?: Module0ExportFile | null;
  [key: string]: Module0ExportFile | null | undefined;
};

export type KeywordOpportunity = {
  keyword: string;
  cluster_id: string | null;
  intent: string;
  priority: string;
  search_volume: number;
  keyword_difficulty: number;
  cpc: number | null;
  current_position: number | null;
  source: string;
  mapped_url: string | null;
  quick_win: boolean;
  ai_answer_trigger_rate: number | null;
  notes: string[];
};

export type KeywordCluster = {
  cluster_id: string;
  label: string;
  intent: string;
  primary_keyword: string;
  keywords: string[];
  total_search_volume: number;
  suggested_url: string | null;
};

export type UrlArchitectureItem = {
  hierarchy_level: string;
  page_type: string;
  current_url: string | null;
  proposed_url: string;
  primary_keyword: string;
  secondary_keywords: string[];
  search_volume: number;
  current_ranking: number | null;
  status: string;
  priority: string;
  ai_answer_trigger_rate: number | null;
  fan_out_coverage: number | null;
};

export type QuickWinSummary = {
  keywords: KeywordOpportunity[];
  total_count: number;
};

export type CompetitorRecord = {
  domain: string;
  source: string;
  anomaly_filtered: boolean;
  competition_level: number | null;
  shared_keywords: number | null;
  keyword_sample: string[];
  notes: string[];
};

export type CompetitorGap = {
  gap_type: string;
  label: string;
  supporting_keywords: string[];
  rationale: string;
  opportunity_score: number;
};

export type MinimumEffortPoint = {
  proposed_url: string;
  primary_keyword: string;
  required_links: number;
  average_competitor_difficulty: number;
  monthly_link_velocity: number;
  notes: string[];
};

export type AiSovEngineResult = {
  engine: string;
  status: string;
  target_queries: number;
  cited_queries: number;
  score: number;
  notes: string[];
};

export type AiSovQueryResult = {
  engine: string;
  keyword: string;
  cited: boolean;
  competitor_cited: string[];
  citation_domains: string[];
  confidence: number;
  notes: string[];
};

export type FanOutSubQuery = {
  query: string;
  content_requirement: string;
  has_content: boolean;
  source: string;
};

export type FanOutKeywordMap = {
  root_keyword: string;
  sub_queries: FanOutSubQuery[];
  invisible_keywords: string[];
  coverage_score: number;
};

export type EntityMention = {
  source_name: string;
  source_url: string | null;
  mention_type: string;
  consistent: boolean;
};

export type RunMessage = {
  code: string;
  severity: string;
  message: string;
  source: string;
};

export type Module0Response = {
  request: {
    website_url: string;
    domain: string | null;
    target_country: string;
    brand_name: string;
    business_type: string;
    services_or_products: string[];
    target_locations: string[];
    business_goals: string[];
    priority_services: string[];
    known_competitors: string[];
    excluded_services_or_pages: string[];
    brand_profiles: string[];
    notes: string | null;
  };
  cdd_file: {
    filename: string;
    content_type: string;
    size_bytes: number;
    extension: string;
  };
  cdd_extraction: {
    text_preview: string;
    sections_detected: string[];
    parser_used: string;
    warnings: string[];
  };
  site_classification: {
    business_type: string;
    detected_domain: string;
    industry_category: string;
    geographic_target: string;
    language: string;
    cms: string;
    cms_version: string | null;
    site_scale_tier: string;
    page_builder: string | null;
    sitemap_url: string | null;
    active_components: string[];
    theme_or_template: string | null;
    confidence_score: number;
    notes: string[];
  };
  website_profile: {
    homepage_status_code: number | null;
    final_status_code: number | null;
    response_time_ms: number | null;
    redirect_count: number;
    homepage_title: string | null;
    meta_description: string | null;
    homepage_text_excerpt: string | null;
    canonical_url: string | null;
    word_count: number;
    h1_count: number;
    primary_schema_type: string | null;
    mobile_friendly: boolean | null;
    broken_internal_links: string[];
    indexable: boolean | null;
    important_headers: Record<string, string>;
    detected_schema_types: string[];
    social_profile_links: string[];
    robots_txt: {
      url: string;
      fetched: boolean;
      status_code: number | null;
      allows_ai_crawlers: boolean | null;
      blocked_agents: string[];
      sitemap_directives: string[];
      notes: string[];
    };
    sitemap: {
      discovered: boolean;
      sitemap_urls: string[];
      fetched_count: number;
      url_count: number;
      sample_urls: string[];
      notes: string[];
    };
    url_inventory: {
      total_urls: number;
      discovered_urls?: string[];
      sample_urls: string[];
      top_sections: Array<{ section: string; url_count: number }>;
      service_like_urls: string[];
      location_like_urls: string[];
      notes: string[];
    };
  };
  semrush: {
    configured: boolean;
    region_database: string;
    status: string;
    data_source: string;
    fallback_used: boolean;
    is_estimated?: boolean;
    warning_message: string | null;
    keyword_limit: number | null;
    notes: string[];
    estimated_monthly_traffic: number | null;
    estimated_monthly_traffic_history: number[];
    organic_keyword_count: number | null;
    competitors_evaluated: number;
    source_file_name?: string | null;
    source_file_extension?: string | null;
    raw_keyword_rows?: number | null;
    accepted_keyword_rows?: number | null;
    rejected_keyword_rows?: number | null;
    rejected_keyword_examples?: string[];
  };
  competitive_intelligence: {
    top_competitors: CompetitorRecord[];
    filtered_domains: string[];
    service_gaps: CompetitorGap[];
    content_gaps: CompetitorGap[];
    local_page_competitors: Record<string, string[]>;
  };
  master_keyword_universe: KeywordOpportunity[];
  keyword_universe_preview: KeywordOpportunity[];
  keyword_clusters: KeywordCluster[];
  quick_wins: QuickWinSummary;
  tam_estimate: number;
  tam_dataset: {
    total_monthly_search_volume: number;
    p1_p2_search_volume: number;
    current_capture_estimate: number;
    opportunity_gap: number;
    current_share_ratio: number;
    methodology: string;
  };
  url_architecture_map: UrlArchitectureItem[];
  url_architecture_preview: UrlArchitectureItem[];
  minimum_effort_points: MinimumEffortPoint[];
  ai_sov_baseline: {
    overall_score: number;
    status: string;
    methodology: string;
    engine_results: AiSovEngineResult[];
    query_results: AiSovQueryResult[];
    missing_visibility_keywords: string[];
  };
  fan_out_map: {
    methodology: string;
    average_coverage: number;
    keyword_maps: FanOutKeywordMap[];
  };
  entity_authority_baseline: {
    score: number;
    knowledge_panel_status: string;
    same_as_links: string[];
    brand_mentions: EntityMention[];
    consistency_gaps: string[];
    reinforcement_opportunities: string[];
    methodology: string;
  };
  exports: Module0Exports;
  warnings_errors: RunMessage[];
  run_timestamps: {
    started_at: string;
    completed_at: string;
    data_fresh_until: string | null;
  };
  next_steps: string[];
};
