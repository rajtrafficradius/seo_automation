from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

from tr_seo_contracts.module0 import UrlInventorySection, UrlInventorySummary


class UrlInventoryService:
    def summarize(self, urls: list[str], excluded_pages: list[str] | None = None) -> UrlInventorySummary:
        excluded_pages = excluded_pages or []
        sections: Counter[str] = Counter()
        service_like_urls: list[str] = []
        location_like_urls: list[str] = []

        for url in urls:
            parsed = urlparse(url)
            parts = [part for part in parsed.path.split("/") if part]
            section = parts[0] if parts else "homepage"
            sections[section] += 1

            lowered = parsed.path.lower()
            if any(token in lowered for token in ["service", "repair", "replacement", "installation"]):
                service_like_urls.append(url)
            if any(token in lowered for token in ["melbourne", "sydney", "brisbane", "perth", "adelaide"]):
                location_like_urls.append(url)

        top_sections = [
            UrlInventorySection(section=section, url_count=count)
            for section, count in sections.most_common(8)
        ]

        notes = []
        if excluded_pages:
            notes.append("Excluded service/page hints were captured from the onboarding input.")

        return UrlInventorySummary(
            total_urls=len(urls),
            discovered_urls=urls[:500],
            sample_urls=urls[:25],
            top_sections=top_sections,
            service_like_urls=service_like_urls[:25],
            location_like_urls=location_like_urls[:25],
            notes=notes,
        )
