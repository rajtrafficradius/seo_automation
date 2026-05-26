from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from tr_seo_contracts.module0 import RobotsTxtStatus


AI_AGENTS = [
    "gptbot",
    "claudebot",
    "perplexitybot",
    "google-extended",
    "google-agent",
]

USER_AGENT = "TRModule0Crawler/1.0 (+https://trafficradius.com.au/seo-automation; respectful crawl for SEO discovery)"


class RobotsInspector:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self.http_client = http_client

    def inspect(self, website_url: str) -> RobotsTxtStatus:
        parsed = urlparse(website_url)
        robots_url = f"{parsed.scheme or 'https'}://{parsed.netloc}/robots.txt"

        try:
            with self._client() as client:
                response = client.get(
                    robots_url,
                    follow_redirects=True,
                    headers={"User-Agent": USER_AGENT, "Accept-Language": "en-AU,en;q=0.9"},
                )
        except httpx.HTTPError as error:
            return RobotsTxtStatus(
                url=robots_url,
                fetched=False,
                notes=[f"robots.txt request failed: {error.__class__.__name__}"],
            )

        if response.status_code >= 400:
            return RobotsTxtStatus(
                url=robots_url,
                fetched=False,
                status_code=response.status_code,
                notes=["robots.txt could not be fetched."],
            )

        text = response.text
        sitemap_directives, blocked_agents = self._parse(text)
        return RobotsTxtStatus(
            url=robots_url,
            fetched=True,
            status_code=response.status_code,
            allows_ai_crawlers=not bool(blocked_agents),
            blocked_agents=blocked_agents,
            sitemap_directives=sitemap_directives,
            notes=["robots.txt fetched and parsed successfully."],
        )

    def _parse(self, text: str) -> tuple[list[str], list[str]]:
        sitemap_directives: list[str] = []
        blocked_agents: list[str] = []
        current_agents: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            lowered_key = key.lower()
            lowered_value = value.lower()

            if lowered_key == "user-agent":
                current_agents = [lowered_value]
                continue

            if lowered_key == "sitemap" and value:
                sitemap_directives.append(value)
                continue

            if lowered_key == "disallow" and value == "/":
                for agent in current_agents or ["*"]:
                    if agent == "*" or agent in AI_AGENTS:
                        blocked_agents.append(agent)

        normalized = []
        seen: set[str] = set()
        for agent in blocked_agents:
            if agent in seen:
                continue
            seen.add(agent)
            normalized.append(agent)
        return sitemap_directives, normalized

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
