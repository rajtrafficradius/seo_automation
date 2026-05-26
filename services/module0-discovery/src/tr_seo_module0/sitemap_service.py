from __future__ import annotations

from collections import deque
import os
from xml.etree import ElementTree as ET

import httpx

from tr_seo_contracts.module0 import SitemapStatus


class SitemapService:
    COMMON_PATHS = [
        "sitemap.xml",
        "sitemap_index.xml",
        "page-sitemap.xml",
        "post-sitemap.xml",
    ]

    def __init__(self, http_client: httpx.Client | None = None, max_urls: int = 120) -> None:
        self.http_client = http_client
        self.max_urls = max_urls

    def discover(self, root_url: str, sitemap_directives: list[str]) -> tuple[SitemapStatus, list[str]]:
        candidates = list(sitemap_directives)
        for path in self.COMMON_PATHS:
            candidates.append(root_url.rstrip("/") + "/" + path)

        discovered_urls: list[str] = []
        sitemap_urls: list[str] = []
        seen_sitemaps: set[str] = set()

        try:
            with self._client() as client:
                queue = deque(candidates)
                while queue and len(discovered_urls) < self.max_urls:
                    sitemap_url = queue.popleft()
                    if not sitemap_url or sitemap_url in seen_sitemaps:
                        continue
                    seen_sitemaps.add(sitemap_url)

                    try:
                        response = client.get(
                            sitemap_url,
                            follow_redirects=True,
                            headers={
                                "User-Agent": "TRModule0Crawler/1.0 (+https://trafficradius.com.au/seo-automation; respectful crawl for SEO discovery)",
                                "Accept-Language": "en-AU,en;q=0.9",
                            },
                        )
                    except httpx.HTTPError:
                        continue

                    if response.status_code >= 400 or not response.text.strip():
                        continue

                    sitemap_urls.append(sitemap_url)
                    nested_sitemaps, urls = self._parse_xml(response.text)
                    for nested in nested_sitemaps:
                        if nested not in seen_sitemaps:
                            queue.append(nested)
                    for url in urls:
                        if url not in discovered_urls:
                            discovered_urls.append(url)
                        if len(discovered_urls) >= self.max_urls:
                            break
        except httpx.HTTPError as error:
            return (
                SitemapStatus(
                    discovered=False,
                    notes=[f"Sitemap discovery failed: {error.__class__.__name__}"],
                ),
                [],
            )

        status = SitemapStatus(
            discovered=bool(sitemap_urls),
            sitemap_urls=sitemap_urls[:10],
            fetched_count=len(sitemap_urls),
            url_count=len(discovered_urls),
            sample_urls=discovered_urls[:25],
            notes=["Sitemap discovery completed." if sitemap_urls else "No sitemap could be confirmed."],
        )
        return status, discovered_urls

    def _parse_xml(self, text: str) -> tuple[list[str], list[str]]:
        nested_sitemaps: list[str] = []
        urls: list[str] = []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return nested_sitemaps, urls

        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}", 1)[0] + "}"

        for child in root:
            if child.tag == f"{namespace}sitemap":
                loc = child.findtext(f"{namespace}loc")
                if loc:
                    nested_sitemaps.append(loc.strip())
            if child.tag == f"{namespace}url":
                loc = child.findtext(f"{namespace}loc")
                if loc:
                    urls.append(loc.strip())
        return nested_sitemaps, urls

    def _client(self):
        if self.http_client is not None:
            return _SharedClientContext(self.http_client)
        timeout_seconds = self._env_float("MODULE0_NETWORK_TIMEOUT_SECONDS", 8.0)
        return httpx.Client(timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 4.0)))

    def _env_float(self, key: str, default: float) -> float:
        try:
            value = float((os.getenv(key) or "").strip())
        except ValueError:
            return default
        return value if value > 0 else default


class _SharedClientContext:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False
