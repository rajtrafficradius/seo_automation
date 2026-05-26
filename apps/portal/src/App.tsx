import { useState, type FormEvent, type ReactNode } from "react";
import { submitModule0 } from "./lib/api";
import type { Module0ExportFile, Module0Response } from "./types/module0";

const defaultValues = {
  websiteUrl: "",
  domain: "",
  targetCountry: "au",
  brandName: "",
  businessType: "unknown",
  servicesOrProducts: "",
  targetLocations: "",
  businessGoals: "",
  priorityServices: "",
  knownCompetitors: "",
  excludedServicesOrPages: "",
  brandProfiles: "",
  notes: ""
};

const exportLabels: Record<string, string> = {
  cdd_extraction: "CDD Extraction",
  site_classification: "Site Classification",
  website_profile: "Website Profile",
  semrush_snapshot: "SEMrush Snapshot",
  competitive_intelligence: "Competitor Intelligence",
  keyword_universe: "Keyword Universe",
  keyword_clusters: "Keyword Clusters",
  quick_wins: "Quick Wins",
  tam_dataset: "TAM Dataset",
  url_architecture_map: "URL Architecture",
  minimum_effort_points: "Minimum Effort Points",
  ai_sov_baseline: "AI SOV Baseline",
  fan_out_map: "Fan-Out Map",
  entity_authority_baseline: "Entity Authority Baseline",
  warnings_errors: "Warnings and Timestamps",
  full_run_workbook: "Full Workbook"
};

export default function App() {
  const [values, setValues] = useState(defaultValues);
  const [file, setFile] = useState<File | null>(null);
  const [semrushKeywordFile, setSemrushKeywordFile] = useState<File | null>(null);
  const [result, setResult] = useState<Module0Response | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Upload a CDD file before submitting.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await submitModule0(values, file, semrushKeywordFile);
      setResult(response);
    } catch (submissionError) {
      setError(
        submissionError instanceof Error ? submissionError.message : "Module 0 submission failed."
      );
    } finally {
      setLoading(false);
    }
  }

  const exportEntries = result
    ? Object.entries(result.exports).filter(
        (entry): entry is [string, Module0ExportFile] => Boolean(entry[1]?.download_url)
      )
    : [];

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col gap-8 px-4 py-8 md:px-6 xl:px-8">
      <section className="rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur">
        <p className="text-sm uppercase tracking-[0.35em] text-amber-300">Module 0</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">Discovery and Keyword Mapping</h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-200">
          Collect structured onboarding inputs, upload the CDD, and review all major Module 0
          outputs with individual Excel downloads plus a full workbook export.
        </p>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.92fr)_minmax(0,1.08fr)]">
        <form
          onSubmit={handleSubmit}
          className="min-w-0 space-y-5 rounded-3xl border border-white/10 bg-slate-950/60 p-6"
        >
          <Field
            label="Website URL"
            value={values.websiteUrl}
            onChange={(value) => setValues((current) => ({ ...current, websiteUrl: value }))}
            placeholder="https://example.com"
          />
          <Field
            label="Domain"
            value={values.domain}
            onChange={(value) => setValues((current) => ({ ...current, domain: value }))}
            placeholder="example.com"
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Target Country"
              value={values.targetCountry}
              onChange={(value) => setValues((current) => ({ ...current, targetCountry: value }))}
              placeholder="au"
            />
            <SelectField
              label="Business Type"
              value={values.businessType}
              onChange={(value) => setValues((current) => ({ ...current, businessType: value }))}
              options={["unknown", "service", "ecommerce", "saas", "local", "hybrid"]}
            />
          </div>
          <Field
            label="Brand Name"
            value={values.brandName}
            onChange={(value) => setValues((current) => ({ ...current, brandName: value }))}
            placeholder="Traffic Radius"
          />
          <TextareaField
            label="Services or Products"
            value={values.servicesOrProducts}
            onChange={(value) =>
              setValues((current) => ({ ...current, servicesOrProducts: value }))
            }
            placeholder="SEO, local SEO, ecommerce SEO"
          />
          <TextareaField
            label="Target Locations"
            value={values.targetLocations}
            onChange={(value) =>
              setValues((current) => ({ ...current, targetLocations: value }))
            }
            placeholder="Sydney, Melbourne"
          />
          <TextareaField
            label="Business Goals"
            value={values.businessGoals}
            onChange={(value) => setValues((current) => ({ ...current, businessGoals: value }))}
            placeholder="Increase organic leads, build AI visibility"
          />
          <TextareaField
            label="Priority Services"
            value={values.priorityServices}
            onChange={(value) =>
              setValues((current) => ({ ...current, priorityServices: value }))
            }
            placeholder="Local SEO, enterprise SEO"
          />
          <TextareaField
            label="Known Competitors"
            value={values.knownCompetitors}
            onChange={(value) =>
              setValues((current) => ({ ...current, knownCompetitors: value }))
            }
            placeholder="competitor-one.com, competitor-two.com"
          />
          <TextareaField
            label="Excluded Services or Pages"
            value={values.excludedServicesOrPages}
            onChange={(value) =>
              setValues((current) => ({ ...current, excludedServicesOrPages: value }))
            }
            placeholder="legacy pages, discontinued services"
          />
          <TextareaField
            label="Brand Profiles"
            value={values.brandProfiles}
            onChange={(value) => setValues((current) => ({ ...current, brandProfiles: value }))}
            placeholder="linkedin.com/company/example, g.page/example"
          />
          <TextareaField
            label="Notes"
            value={values.notes}
            onChange={(value) => setValues((current) => ({ ...current, notes: value }))}
            placeholder="Any context from the account manager"
          />
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-100">CDD Upload</label>
            <input
              type="file"
              accept=".pdf,.docx,.xlsx,.xls,.csv"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-2xl border border-dashed border-amber-300/40 bg-slate-900/60 p-4 text-sm text-slate-200"
            />
            <p className="text-xs text-slate-400">
              Supported formats: PDF, DOCX, XLSX, XLS, CSV.
            </p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-100">
              SEMrush Keyword Upload (Optional)
            </label>
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(event) => setSemrushKeywordFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-2xl border border-dashed border-cyan-300/40 bg-slate-900/60 p-4 text-sm text-slate-200"
            />
            <p className="text-xs text-slate-400">
              Use a manually downloaded SEMrush keyword export while live SEMrush credits are
              unavailable.
            </p>
          </div>

          {error ? <p className="text-sm text-rose-300">{error}</p> : null}

          <button
            type="submit"
            disabled={loading}
            className="rounded-full bg-amber-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-300 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Running Module 0..." : "Run Module 0"}
          </button>
        </form>

        <section className="min-w-0 rounded-3xl border border-white/10 bg-white/5 p-6">
          <h2 className="text-xl font-semibold text-white">Module 0 Review Panel</h2>
          {!result ? (
            <p className="mt-4 text-sm leading-6 text-slate-300">
              Submit the onboarding form to review the full Module 0 response, inspect each output
              bucket, and download separate Excel files for every major dataset.
            </p>
          ) : (
            <div className="mt-4 space-y-5 text-sm text-slate-200">
              <InfoCard title="All Downloads">
                <div className="grid gap-2 lg:grid-cols-2">
                  {exportEntries.map(([key, fileEntry]) => (
                    <a
                      key={key}
                      href={fileEntry.download_url}
                      className="inline-flex min-w-0 items-center justify-between gap-3 rounded-2xl bg-slate-900/70 px-4 py-3 text-xs font-semibold text-slate-100 transition hover:bg-slate-900"
                    >
                      <span className="min-w-0 break-words text-left">{exportLabels[key] ?? key}</span>
                      <span className="shrink-0 text-amber-300">XLSX</span>
                    </a>
                  ))}
                </div>
              </InfoCard>

              <InfoCard title="CDD Parser">
                <p>Parser: {result.cdd_extraction.parser_used}</p>
                <p className="mt-1">Sections: {formatList(result.cdd_extraction.sections_detected)}</p>
                <p className="mt-2 whitespace-pre-wrap text-slate-300">
                  {result.cdd_extraction.text_preview || "No preview extracted."}
                </p>
                {result.cdd_extraction.warnings.length ? (
                  <ul className="mt-3 space-y-2">
                    {result.cdd_extraction.warnings.map((warning) => (
                      <li key={warning} className="rounded-2xl bg-slate-900/60 px-3 py-2 text-amber-300">
                        {warning}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </InfoCard>

              <InfoCard title="Site Classification">
                <KeyValueGrid
                  rows={[
                    ["Domain", result.site_classification.detected_domain],
                    ["Business Type", result.site_classification.business_type],
                    ["Industry Category", result.site_classification.industry_category],
                    ["Geographic Target", result.site_classification.geographic_target],
                    ["Language", result.site_classification.language],
                    ["CMS", result.site_classification.cms],
                    ["CMS Version", result.site_classification.cms_version ?? "n/a"],
                    ["Site Scale", result.site_classification.site_scale_tier],
                    ["Page Builder", result.site_classification.page_builder ?? "n/a"],
                    ["Sitemap", result.site_classification.sitemap_url ?? "Pending"],
                    ["Theme", result.site_classification.theme_or_template ?? "n/a"],
                    ["Confidence", result.site_classification.confidence_score.toFixed(2)]
                  ]}
                />
                <p className="mt-3 text-slate-300">
                  Active Components: {formatList(result.site_classification.active_components)}
                </p>
              </InfoCard>

              <InfoCard title="Website Profile">
                <KeyValueGrid
                  rows={[
                    ["Homepage Status", String(result.website_profile.homepage_status_code ?? "n/a")],
                    ["Final Status", String(result.website_profile.final_status_code ?? "n/a")],
                    ["Response Time", `${result.website_profile.response_time_ms ?? "n/a"} ms`],
                    ["Redirect Count", String(result.website_profile.redirect_count ?? 0)],
                    ["Title", result.website_profile.homepage_title ?? "n/a"],
                    ["Meta Description", result.website_profile.meta_description ?? "n/a"],
                    ["Canonical", result.website_profile.canonical_url ?? "n/a"],
                    ["Word Count", String(result.website_profile.word_count ?? 0)],
                    ["H1 Count", String(result.website_profile.h1_count ?? 0)],
                    ["Primary Schema", result.website_profile.primary_schema_type ?? "n/a"],
                    ["Mobile Friendly", formatBoolean(result.website_profile.mobile_friendly)],
                    ["Indexable", formatBoolean(result.website_profile.indexable)],
                    ["Robots", `${result.website_profile.robots_txt.status_code ?? "n/a"} / ${String(result.website_profile.robots_txt.fetched)}`],
                    ["Sitemaps", String(result.website_profile.sitemap.sitemap_urls.length)],
                    ["URL Count", String(result.website_profile.url_inventory.total_urls)]
                  ]}
                />
                <p className="mt-3 text-slate-300">
                  Broken Internal Links:{" "}
                  {result.website_profile.broken_internal_links.length
                    ? result.website_profile.broken_internal_links.join(", ")
                    : "none found in safe crawl sample"}
                </p>
                <p className="mt-3 text-slate-300">
                  Schema Types: {formatList(result.website_profile.detected_schema_types)}
                </p>
                <p className="mt-1 text-slate-300">
                  Sample URLs: {formatList(result.website_profile.url_inventory.sample_urls.slice(0, 5))}
                </p>
              </InfoCard>

              <InfoCard title="SEMrush">
                <KeyValueGrid
                  rows={[
                    ["Status", result.semrush.status],
                    ["Configured", String(result.semrush.configured)],
                    ["Source", result.semrush.data_source],
                    ["Region", result.semrush.region_database],
                    ["Keyword Limit", String(result.semrush.keyword_limit ?? "n/a")],
                    ["Source File", result.semrush.source_file_name ?? "n/a"],
                    ["Raw Upload Rows", String(result.semrush.raw_keyword_rows ?? "n/a")],
                    ["Accepted Rows", String(result.semrush.accepted_keyword_rows ?? "n/a")],
                    ["Rejected Rows", String(result.semrush.rejected_keyword_rows ?? "n/a")],
                    ["Estimated Traffic", String(result.semrush.estimated_monthly_traffic ?? "n/a")],
                    ["Organic Keywords", String(result.semrush.organic_keyword_count ?? "n/a")],
                    ["Competitors Evaluated", String(result.semrush.competitors_evaluated)]
                  ]}
                />
                {result.semrush.warning_message ? (
                  <p className="mt-3 rounded-2xl bg-slate-900/60 px-3 py-2 text-amber-300">
                    {result.semrush.warning_message}
                  </p>
                ) : null}
                {result.semrush.rejected_keyword_examples?.length ? (
                  <p className="mt-3 text-slate-300">
                    Rejected Examples: {formatList(result.semrush.rejected_keyword_examples)}
                  </p>
                ) : null}
              </InfoCard>

              <InfoCard title="Competitor Intelligence">
                <p>Top Competitors: {result.competitive_intelligence.top_competitors.length}</p>
                <ul className="mt-3 space-y-2">
                  {result.competitive_intelligence.top_competitors.slice(0, 5).map((item) => (
                    <li key={item.domain} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <p className="font-medium text-white">{item.domain}</p>
                      <p className="mt-1 text-slate-300">
                        Level: {item.competition_level ?? "n/a"} | Shared keywords:{" "}
                        {item.shared_keywords ?? "n/a"}
                      </p>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-slate-300">
                  Service Gaps: {result.competitive_intelligence.service_gaps.length} | Content
                  Gaps: {result.competitive_intelligence.content_gaps.length}
                </p>
              </InfoCard>

              <InfoCard title="Keyword Universe Preview">
                <p>Total Keywords: {result.master_keyword_universe.length}</p>
                <ul className="mt-3 space-y-2">
                  {result.keyword_universe_preview.slice(0, 8).map((item) => (
                    <li key={item.keyword} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <span className="font-medium text-white">{item.keyword}</span>
                      <span className="ml-2 text-xs text-amber-300">{item.priority}</span>
                      <p className="mt-1 text-slate-300">
                        Vol: {item.search_volume} | KD: {item.keyword_difficulty} | Pos:{" "}
                        {item.current_position ?? "n/a"}
                      </p>
                    </li>
                  ))}
                </ul>
              </InfoCard>

              <InfoCard title="Keyword Clusters">
                <ul className="space-y-2">
                  {result.keyword_clusters.slice(0, 6).map((cluster) => (
                    <li key={cluster.cluster_id} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <p className="font-medium text-white">{cluster.label}</p>
                      <p className="mt-1 text-slate-300">
                        Primary: {cluster.primary_keyword} | Volume: {cluster.total_search_volume}
                      </p>
                    </li>
                  ))}
                </ul>
              </InfoCard>

              <InfoCard title="Quick Wins">
                <p>Total Quick Wins: {result.quick_wins.total_count}</p>
                <ul className="mt-3 space-y-2">
                  {result.quick_wins.keywords.slice(0, 6).map((item) => (
                    <li key={item.keyword} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <span className="font-medium text-white">{item.keyword}</span>
                      <p className="mt-1 text-slate-300">
                        Vol: {item.search_volume} | KD: {item.keyword_difficulty} | Pos:{" "}
                        {item.current_position ?? "n/a"}
                      </p>
                    </li>
                  ))}
                </ul>
              </InfoCard>

              <InfoCard title="TAM Dataset">
                <KeyValueGrid
                  rows={[
                    ["Total Monthly Search Volume", String(result.tam_dataset.total_monthly_search_volume)],
                    ["P1 + P2 Search Volume", String(result.tam_dataset.p1_p2_search_volume)],
                    ["Current Capture", String(result.tam_dataset.current_capture_estimate)],
                    ["Opportunity Gap", String(result.tam_dataset.opportunity_gap)],
                    ["Share Ratio", result.tam_dataset.current_share_ratio.toFixed(2)]
                  ]}
                />
                <p className="mt-3 text-slate-300">{result.tam_dataset.methodology}</p>
              </InfoCard>

              <InfoCard title="URL Architecture Preview">
                <ul className="space-y-2">
                  {result.url_architecture_preview.slice(0, 8).map((item) => (
                    <li key={item.proposed_url} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <span className="font-medium text-white">{item.proposed_url}</span>
                      <span className="ml-2 text-xs text-slate-400">{item.page_type}</span>
                      <p className="mt-1 text-slate-300">
                        Primary: {item.primary_keyword} | Volume: {item.search_volume}
                      </p>
                    </li>
                  ))}
                </ul>
              </InfoCard>

              <InfoCard title="Minimum Effort Points">
                <ul className="space-y-2">
                  {result.minimum_effort_points.slice(0, 6).map((item) => (
                    <li key={item.proposed_url} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <p className="font-medium text-white">{item.proposed_url}</p>
                      <p className="mt-1 text-slate-300">
                        Links: {item.required_links} | Avg difficulty:{" "}
                        {item.average_competitor_difficulty} | Velocity:{" "}
                        {item.monthly_link_velocity}/mo
                      </p>
                    </li>
                  ))}
                </ul>
              </InfoCard>

              <InfoCard title="AI SOV Baseline">
                <KeyValueGrid
                  rows={[
                    ["Status", result.ai_sov_baseline.status],
                    ["Overall Score", result.ai_sov_baseline.overall_score.toFixed(2)],
                    ["Tracked Queries", String(result.ai_sov_baseline.query_results.length)],
                    ["Missing Visibility Keywords", String(result.ai_sov_baseline.missing_visibility_keywords.length)]
                  ]}
                />
                <ul className="mt-3 space-y-2">
                  {result.ai_sov_baseline.engine_results.map((engine) => (
                    <li key={engine.engine} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <p className="font-medium text-white">{engine.engine}</p>
                      <p className="mt-1 text-slate-300">
                        Status: {engine.status} | Score: {engine.score.toFixed(2)} | Queries:{" "}
                        {engine.cited_queries}/{engine.target_queries}
                      </p>
                    </li>
                  ))}
                </ul>
              </InfoCard>

              <InfoCard title="Fan-Out Map">
                <p>Average Coverage: {result.fan_out_map.average_coverage.toFixed(2)}</p>
                <ul className="mt-3 space-y-2">
                  {result.fan_out_map.keyword_maps.slice(0, 5).map((item) => (
                    <li key={item.root_keyword} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <p className="font-medium text-white">{item.root_keyword}</p>
                      <p className="mt-1 text-slate-300">
                        Coverage: {item.coverage_score.toFixed(2)} | Invisible keywords:{" "}
                        {item.invisible_keywords.length}
                      </p>
                    </li>
                  ))}
                </ul>
              </InfoCard>

              <InfoCard title="Entity Authority Baseline">
                <KeyValueGrid
                  rows={[
                    ["Score", String(result.entity_authority_baseline.score)],
                    ["Knowledge Panel", result.entity_authority_baseline.knowledge_panel_status],
                    ["sameAs Links", String(result.entity_authority_baseline.same_as_links.length)],
                    ["Brand Mentions", String(result.entity_authority_baseline.brand_mentions.length)]
                  ]}
                />
                <p className="mt-3 text-slate-300">
                  Consistency Gaps: {formatList(result.entity_authority_baseline.consistency_gaps)}
                </p>
                <p className="mt-1 text-slate-300">
                  Opportunities:{" "}
                  {formatList(result.entity_authority_baseline.reinforcement_opportunities)}
                </p>
              </InfoCard>

              <InfoCard title="Warnings and Timestamps">
                <ul className="space-y-2">
                  {result.warnings_errors.map((item) => (
                    <li key={`${item.code}-${item.source}`} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      <p className="font-medium text-white">
                        {item.code} <span className="ml-2 text-xs text-amber-300">{item.severity}</span>
                      </p>
                      <p className="mt-1 text-slate-300">{item.message}</p>
                    </li>
                  ))}
                </ul>
                <div className="mt-3 space-y-1 text-slate-300">
                  <p>Started: {result.run_timestamps.started_at}</p>
                  <p>Completed: {result.run_timestamps.completed_at}</p>
                  <p>Fresh Until: {result.run_timestamps.data_fresh_until ?? "n/a"}</p>
                </div>
                <ul className="mt-3 space-y-2">
                  {result.next_steps.map((step) => (
                    <li key={step} className="rounded-2xl bg-slate-900/60 px-3 py-2">
                      {step}
                    </li>
                  ))}
                </ul>
              </InfoCard>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

type FieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
};

function Field({ label, value, onChange, placeholder }: FieldProps) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-slate-100">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm text-white outline-none ring-0 placeholder:text-slate-500"
      />
    </label>
  );
}

type TextareaFieldProps = FieldProps;

function TextareaField({ label, value, onChange, placeholder }: TextareaFieldProps) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-slate-100">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={3}
        className="w-full rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm text-white outline-none ring-0 placeholder:text-slate-500"
      />
    </label>
  );
}

type SelectFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
};

function SelectField({ label, value, onChange, options }: SelectFieldProps) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-slate-100">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm text-white outline-none"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function InfoCard(props: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-950/60 p-4">
      <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-300">
        {props.title}
      </h3>
      <div className="mt-3">{props.children}</div>
    </section>
  );
}

function KeyValueGrid(props: { rows: Array<[string, string]> }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {props.rows.map(([label, value]) => (
        <div key={label} className="rounded-2xl bg-slate-900/60 px-3 py-2">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{label}</p>
          <p className="mt-1 text-slate-100">{value}</p>
        </div>
      ))}
    </div>
  );
}

function formatList(values: string[]) {
  return values.length ? values.join(", ") : "n/a";
}

function formatBoolean(value: boolean | null | undefined) {
  if (value === true) {
    return "yes";
  }
  if (value === false) {
    return "no";
  }
  return "n/a";
}
