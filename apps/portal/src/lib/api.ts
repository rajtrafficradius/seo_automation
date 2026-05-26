import type { Module0FormValues, Module0Response } from "../types/module0";
import { createMockModule0Response } from "./mockModule0";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  (typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:8000");

export async function submitModule0(
  values: Module0FormValues,
  cddFile: File,
  semrushKeywordFile?: File | null
): Promise<Module0Response> {
  const formData = new FormData();
  formData.append("website_url", values.websiteUrl);
  formData.append("domain", values.domain);
  formData.append("target_country", values.targetCountry);
  formData.append("brand_name", values.brandName);
  formData.append("business_type", values.businessType);
  formData.append("services_or_products", values.servicesOrProducts);
  formData.append("target_locations", values.targetLocations);
  formData.append("business_goals", values.businessGoals);
  formData.append("priority_services", values.priorityServices);
  formData.append("known_competitors", values.knownCompetitors);
  formData.append("excluded_services_or_pages", values.excludedServicesOrPages);
  formData.append("brand_profiles", values.brandProfiles);
  formData.append("notes", values.notes);
  formData.append("cdd_file", cddFile);
  if (semrushKeywordFile) {
    formData.append("semrush_keyword_file", semrushKeywordFile);
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/module0/runs`, {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error(errorBody || "Module 0 request failed.");
    }

    return (await response.json()) as Module0Response;
  } catch (error) {
    if (error instanceof TypeError) {
      return createMockModule0Response(values, cddFile);
    }
    throw error;
  }
}
