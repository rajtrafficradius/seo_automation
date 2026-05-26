import type {
  CompetitorRecord,
  KeywordCluster,
  KeywordOpportunity,
  MinimumEffortPoint,
  Module0FormValues,
  Module0Response,
  UrlArchitectureItem
} from "../types/module0";

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function safeDomainFromUrl(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function mockExport(filename: string) {
  return {
    filename,
    content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    download_url: "#"
  };
}

export function createMockModule0Response(
  values: Module0FormValues,
  cddFile: File
): Module0Response {
  const services = splitCsv(values.servicesOrProducts || values.brandName).slice(0, 6);
  const locations = splitCsv(values.targetLocations || "Melbourne");
  const goals = splitCsv(values.businessGoals);
  const domain = values.domain || safeDomainFromUrl(values.websiteUrl);
  const businessType = values.businessType || "unknown";

  const keywords: KeywordOpportunity[] = services.flatMap((service, index) => [
    {
      keyword: service.toLowerCase(),
      cluster_id: slugify(service),
      intent: "transactional",
      priority: "P1",
      search_volume: 150 + index * 20,
      keyword_difficulty: 25 + index * 5,
      cpc: 6 + index,
      current_position: 12 + index,
      source: "mock-seed",
      mapped_url:
        businessType === "ecommerce"
          ? `/collections/${slugify(service)}`
          : `/services/${slugify(service)}`,
      quick_win: index < 2,
      ai_answer_trigger_rate: 0.25 + index * 0.03,
      notes: ["Frontend mock mode preview."]
    },
    {
      keyword: `${values.brandName} ${service}`.trim().toLowerCase(),
      cluster_id: slugify(service),
      intent: "transactional",
      priority: "P2",
      search_volume: 80 + index * 10,
      keyword_difficulty: 20 + index * 4,
      cpc: 4.5 + index,
      current_position: 18 + index,
      source: "mock-brand-seed",
      mapped_url:
        businessType === "ecommerce"
          ? `/collections/${slugify(service)}`
          : `/services/${slugify(service)}`,
      quick_win: false,
      ai_answer_trigger_rate: 0.2 + index * 0.02,
      notes: ["Frontend mock mode preview."]
    }
  ]);

  const keywordClusters: KeywordCluster[] = services.map((service, index) => ({
    cluster_id: slugify(service),
    label: service,
    intent: "transactional",
    primary_keyword: service.toLowerCase(),
    keywords: keywords.filter((item) => item.cluster_id === slugify(service)).map((item) => item.keyword),
    total_search_volume: 230 + index * 30,
    suggested_url:
      businessType === "ecommerce"
        ? `/collections/${slugify(service)}`
        : `/services/${slugify(service)}`
  }));

  const urlArchitecture: UrlArchitectureItem[] = [
    {
      hierarchy_level: "L1",
      page_type: "homepage",
      current_url: values.websiteUrl || null,
      proposed_url: "/",
      primary_keyword: values.brandName.toLowerCase(),
      secondary_keywords: [],
      search_volume: 0,
      current_ranking: null,
      status: "existing",
      priority: "P2",
      ai_answer_trigger_rate: null,
      fan_out_coverage: null
    },
    ...keywordClusters.map((cluster, index) => ({
      hierarchy_level: "L2",
      page_type: businessType === "ecommerce" ? "category" : "service",
      current_url: null,
      proposed_url: cluster.suggested_url || `/services/${slugify(cluster.label)}`,
      primary_keyword: cluster.primary_keyword,
      secondary_keywords: cluster.keywords.slice(1, 4),
      search_volume: cluster.total_search_volume,
      current_ranking: 10 + index,
      status: "new",
      priority: index < 2 ? "P1" : "P2",
      ai_answer_trigger_rate: 0.3 + index * 0.04,
      fan_out_coverage: 0.2 + index * 0.05
    }))
  ];

  const competitors: CompetitorRecord[] = services.slice(0, 3).map((service, index) => ({
    domain: `${slugify(service)}-competitor-${index + 1}.com.au`,
    source: "mock-llm-style",
    anomaly_filtered: false,
    competition_level: 0.4 + index * 0.1,
    shared_keywords: 12 + index * 6,
    keyword_sample: keywords.slice(index, index + 4).map((item) => item.keyword),
    notes: ["Mock competitor generated for local preview mode."]
  }));

  const minimumEffortPoints: MinimumEffortPoint[] = urlArchitecture.slice(1).map((item, index) => ({
    proposed_url: item.proposed_url,
    primary_keyword: item.primary_keyword,
    required_links: 3 + index,
    average_competitor_difficulty: 24 + index * 6,
    monthly_link_velocity: 1 + index,
    notes: ["Mock off-page baseline for local preview mode."]
  }));

  return {
    request: {
      website_url: values.websiteUrl,
      domain: domain || null,
      target_country: values.targetCountry,
      brand_name: values.brandName,
      business_type: businessType,
      services_or_products: services,
      target_locations: locations,
      business_goals: goals,
      priority_services: splitCsv(values.priorityServices),
      known_competitors: splitCsv(values.knownCompetitors),
      excluded_services_or_pages: splitCsv(values.excludedServicesOrPages),
      brand_profiles: splitCsv(values.brandProfiles),
      notes: values.notes || null
    },
    cdd_file: {
      filename: cddFile.name,
      content_type: cddFile.type || "application/octet-stream",
      size_bytes: cddFile.size,
      extension: cddFile.name.includes(".") ? cddFile.name.slice(cddFile.name.lastIndexOf(".")) : ""
    },
    cdd_extraction: {
      text_preview:
        "Mock mode is active because the local API is not reachable yet. Start the FastAPI server later to replace this with real parsed CDD output.",
      sections_detected: ["business overview", "services", "goals", "competitors"],
      parser_used: "mock-fallback",
      warnings: ["Frontend fallback response used because the backend server was unavailable."]
    },
    site_classification: {
      business_type: businessType,
      detected_domain: domain || "unknown",
      industry_category:
        businessType === "ecommerce"
          ? "catalog_retail"
          : businessType === "service" || businessType === "local"
            ? "local_service_business"
            : "general_business_services",
      geographic_target: locations.length ? `multi_location:${locations.join(", ").toLowerCase()}` : "local_market",
      language: "en",
      cms: "unknown",
      cms_version: null,
      site_scale_tier: "pending-crawl",
      page_builder: null,
      sitemap_url: domain ? `https://${domain}/sitemap.xml` : null,
      active_components: [],
      theme_or_template: null,
      confidence_score: 0.3,
      notes: ["This is preview data generated in frontend mock mode."]
    },
    website_profile: {
      homepage_status_code: 200,
      final_status_code: 200,
      response_time_ms: 320,
      redirect_count: 0,
      homepage_title: values.brandName || "Mock Site",
      meta_description: "Mock mode preview for local Module 0 testing.",
      homepage_text_excerpt:
        "Mock mode summary generated from onboarding inputs so the frontend can preview the full Module 0 structure.",
      canonical_url: values.websiteUrl || null,
      word_count: 420,
      h1_count: 1,
      primary_schema_type: "Organization",
      mobile_friendly: true,
      broken_internal_links: [],
      indexable: true,
      important_headers: {
        server: "mock-server",
        "content-type": "text/html"
      },
      detected_schema_types: ["Organization"],
      social_profile_links: splitCsv(values.brandProfiles),
      robots_txt: {
        url: domain ? `https://${domain}/robots.txt` : "https://example.com/robots.txt",
        fetched: true,
        status_code: 200,
        allows_ai_crawlers: true,
        blocked_agents: [],
        sitemap_directives: domain ? [`https://${domain}/sitemap.xml`] : [],
        notes: ["Mock robots.txt result."]
      },
      sitemap: {
        discovered: true,
        sitemap_urls: domain ? [`https://${domain}/sitemap.xml`] : [],
        fetched_count: 1,
        url_count: Math.max(services.length + 3, 5),
        sample_urls: urlArchitecture.map((item) => item.proposed_url),
        notes: ["Mock sitemap discovery result."]
      },
      url_inventory: {
        total_urls: Math.max(services.length + 3, 5),
        discovered_urls: urlArchitecture.map((item) => item.proposed_url),
        sample_urls: urlArchitecture.map((item) => item.proposed_url),
        top_sections: [
          { section: "homepage", url_count: 1 },
          { section: "services", url_count: services.length }
        ],
        service_like_urls: urlArchitecture.slice(1).map((item) => item.proposed_url),
        location_like_urls: locations.map((location) => `/locations/${slugify(location)}`),
        notes: ["Mock URL inventory summary."]
      }
    },
    semrush: {
      configured: false,
      region_database: values.targetCountry || "au",
      status: "mocked",
      data_source: "mock_frontend",
      fallback_used: true,
      is_estimated: true,
      warning_message: "Frontend mock mode is active because the backend server is unavailable.",
      keyword_limit: 200,
      notes: ["No API key is required just to view the frontend locally."],
      estimated_monthly_traffic: 240,
      estimated_monthly_traffic_history: [180, 210, 240],
      organic_keyword_count: keywords.length,
      competitors_evaluated: competitors.length,
      source_file_name: null,
      source_file_extension: null,
      raw_keyword_rows: null,
      accepted_keyword_rows: null,
      rejected_keyword_rows: null,
      rejected_keyword_examples: []
    },
    competitive_intelligence: {
      top_competitors: competitors,
      filtered_domains: [],
      service_gaps: services.slice(0, 2).map((service, index) => ({
        gap_type: "service_gap",
        label: `${service} comparison`,
        supporting_keywords: [service.toLowerCase()],
        rationale: "Mock local preview identified an underdeveloped service angle.",
        opportunity_score: 60 + index * 10
      })),
      content_gaps: goals.slice(0, 2).map((goal, index) => ({
        gap_type: "content_gap",
        label: goal || `content-gap-${index + 1}`,
        supporting_keywords: keywords.slice(index, index + 2).map((item) => item.keyword),
        rationale: "Mock local preview content opportunity.",
        opportunity_score: 55 + index * 8
      })),
      local_page_competitors: Object.fromEntries(
        urlArchitecture.slice(1, 4).map((item, index) => [
          item.proposed_url,
          competitors.slice(0, 2 + (index % 2)).map((competitor) => competitor.domain)
        ])
      )
    },
    master_keyword_universe: keywords,
    keyword_universe_preview: keywords.slice(0, 8),
    keyword_clusters: keywordClusters,
    quick_wins: {
      keywords: keywords.filter((item) => item.quick_win).slice(0, 4),
      total_count: keywords.filter((item) => item.quick_win).length
    },
    tam_estimate: keywords.reduce((sum, item) => sum + item.search_volume, 0),
    tam_dataset: {
      total_monthly_search_volume: keywords.reduce((sum, item) => sum + item.search_volume, 0),
      p1_p2_search_volume: keywords.reduce((sum, item) => sum + item.search_volume, 0),
      current_capture_estimate: 240,
      opportunity_gap: keywords.reduce((sum, item) => sum + item.search_volume, 0) - 240,
      current_share_ratio: 0.18,
      methodology: "Mock local preview TAM estimate."
    },
    url_architecture_map: urlArchitecture,
    url_architecture_preview: urlArchitecture.slice(0, 6),
    minimum_effort_points: minimumEffortPoints,
    ai_sov_baseline: {
      overall_score: 0.12,
      status: "heuristic",
      methodology: "Mock heuristic AI SOV baseline for local preview mode.",
      engine_results: ["google_ai_overviews", "perplexity", "chatgpt"].map((engine) => ({
        engine,
        status: "heuristic",
        target_queries: 4,
        cited_queries: 0,
        score: 0,
        notes: ["Mock mode uses heuristic AI visibility output."]
      })),
      query_results: keywords.slice(0, 4).flatMap((item) =>
        ["google_ai_overviews", "perplexity", "chatgpt"].map((engine) => ({
          engine,
          keyword: item.keyword,
          cited: false,
          competitor_cited: [],
          citation_domains: [],
          confidence: 0.2,
          notes: ["Mock mode uses heuristic AI visibility output."]
        }))
      ),
      missing_visibility_keywords: keywords.slice(0, 5).map((item) => item.keyword)
    },
    fan_out_map: {
      methodology: "Mock fan-out mapping from seeded keywords.",
      average_coverage: 0.2,
      keyword_maps: keywords.slice(0, 4).map((item) => ({
        root_keyword: item.keyword,
        sub_queries: [
          {
            query: `${item.keyword} reviews`,
            content_requirement: `Create or enrich a section answering ${item.keyword} reviews.`,
            has_content: false,
            source: "mock"
          },
          {
            query: `${item.keyword} pricing`,
            content_requirement: `Create or enrich a section answering ${item.keyword} pricing.`,
            has_content: false,
            source: "mock"
          }
        ],
        invisible_keywords: [`${item.keyword} reviews`, `${item.keyword} pricing`],
        coverage_score: 0.2
      }))
    },
    entity_authority_baseline: {
      score: 28,
      knowledge_panel_status: "not_verified",
      same_as_links: splitCsv(values.brandProfiles),
      brand_mentions: splitCsv(values.brandProfiles).map((profile) => ({
        source_name: profile,
        source_url: profile,
        mention_type: "profile",
        consistent: true
      })),
      consistency_gaps: ["Mock mode detected limited brand corroboration."],
      reinforcement_opportunities: [
        "Add more corroborating profiles and directory listings.",
        "Deploy stronger organization schema."
      ],
      methodology: "Mock entity baseline for local preview mode."
    },
    exports: {
      cdd_extraction: mockExport("mock-cdd_extraction.xlsx"),
      site_classification: mockExport("mock-site_classification.xlsx"),
      website_profile: mockExport("mock-website_profile.xlsx"),
      semrush_snapshot: mockExport("mock-semrush_snapshot.xlsx"),
      competitive_intelligence: mockExport("mock-competitive_intelligence.xlsx"),
      keyword_universe: mockExport("mock-master_keyword_universe.xlsx"),
      keyword_clusters: mockExport("mock-keyword_clusters.xlsx"),
      quick_wins: mockExport("mock-quick_wins.xlsx"),
      tam_dataset: mockExport("mock-tam_dataset.xlsx"),
      url_architecture_map: mockExport("mock-url_architecture_map.xlsx"),
      minimum_effort_points: mockExport("mock-minimum_effort_points.xlsx"),
      ai_sov_baseline: mockExport("mock-ai_sov_baseline.xlsx"),
      fan_out_map: mockExport("mock-fan_out_map.xlsx"),
      entity_authority_baseline: mockExport("mock-entity_authority_baseline.xlsx"),
      warnings_errors: mockExport("mock-warnings_errors.xlsx"),
      full_run_workbook: mockExport("mock-module0_full_export.xlsx")
    },
    warnings_errors: [
      {
        code: "frontend_mock_mode",
        severity: "warning",
        message: "Frontend mock mode is active because the backend server is unavailable.",
        source: "mockModule0"
      }
    ],
    run_timestamps: {
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      data_fresh_until: null
    },
    next_steps: [
      "Start the FastAPI backend on localhost:8000 to replace mock mode with real Module 0 responses.",
      "Add SEMRUSH_API_KEY later when you want live keyword and competitor data.",
      "Use the full workbook and individual exports to validate output quality."
    ]
  };
}
