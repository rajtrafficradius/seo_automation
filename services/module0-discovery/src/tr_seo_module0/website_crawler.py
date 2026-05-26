from __future__ import annotations

import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - requests is optional at runtime until env sync
    requests = None
    HTTPAdapter = None
    Retry = None


USER_AGENT = (
    "TRModule0Crawler/1.0 (+https://trafficradius.com.au/seo-automation; "
    "respectful crawl for SEO discovery)"
)

BLOCKED_MARKERS = [
    "just a moment",
    "attention required",
    "checking your browser",
    "verify you are human",
    "access denied",
    "captcha",
    "security check",
    "please enable cookies",
    "cloudflare",
]

IRRELEVANT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".zip",
    ".mp4",
    ".mp3",
    ".ico",
    ".css",
    ".js",
    ".xml",
}


@dataclass(slots=True)
class CrawledPage:
    url: str
    page_type: str
    status_code: int
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    text_excerpt: str | None = None
    language: str | None = None
    h1_count: int = 0
    word_count: int = 0
    mobile_friendly: bool | None = None
    indexable: bool | None = None
    schema_types: list[str] = field(default_factory=list)
    social_links: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    navigation_labels: list[str] = field(default_factory=list)
    generator: str | None = None
    framework_hints: list[str] = field(default_factory=list)
    discovered_links: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    html: str | None = None


@dataclass(slots=True)
class WebsiteCrawlResult:
    homepage_status_code: int | None = None
    final_status_code: int | None = None
    response_time_ms: int | None = None
    redirect_count: int = 0
    homepage_html: str = ""
    homepage_headers: dict[str, str] = field(default_factory=dict)
    homepage_title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    homepage_text_excerpt: str | None = None
    language: str | None = None
    h1_count: int = 0
    word_count: int = 0
    mobile_friendly: bool | None = None
    broken_internal_links: list[str] = field(default_factory=list)
    indexable: bool | None = None
    schema_types: list[str] = field(default_factory=list)
    social_profile_links: list[str] = field(default_factory=list)
    observed_headings: list[str] = field(default_factory=list)
    navigation_labels: list[str] = field(default_factory=list)
    generator_hints: list[str] = field(default_factory=list)
    framework_hints: list[str] = field(default_factory=list)
    crawled_pages: list[CrawledPage] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    notes: list[str] = field(default_factory=list)


class WebsiteCrawler:
    def __init__(
        self,
        max_pages: int | None = None,
        max_links_per_page: int | None = None,
        request_timeout: float | None = None,
        rate_limit_seconds: float | None = None,
    ) -> None:
        self.max_pages = max_pages or self._env_int("MODULE0_CRAWL_MAX_PAGES", 8)
        self.max_links_per_page = max_links_per_page or self._env_int("MODULE0_CRAWL_MAX_LINKS_PER_PAGE", 16)
        self.request_timeout = request_timeout or self._env_float("MODULE0_CRAWL_TIMEOUT_SECONDS", 8.0)
        self.rate_limit_seconds = rate_limit_seconds or self._env_float("MODULE0_CRAWL_RATE_LIMIT_SECONDS", 0.15)
        self.enable_playwright = os.getenv("MODULE0_ENABLE_PLAYWRIGHT", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        self._requests_cached_session = self._build_requests_session() if requests is not None else None

    def crawl(
        self,
        root_url: str,
        sitemap_urls: list[str],
        excluded_pages: list[str] | None = None,
    ) -> WebsiteCrawlResult:
        excluded_pages = [item.lower().strip() for item in (excluded_pages or []) if item.strip()]
        parser, parser_notes = self._load_robots(root_url)
        result = WebsiteCrawlResult(notes=list(parser_notes))
        normalized_root = self._normalize_url(root_url)

        homepage_allowed = not (parser and not parser.can_fetch(USER_AGENT, root_url))
        if not homepage_allowed:
            result.blocked_reason = "robots_disallow_homepage"
            result.notes.append(
                "Homepage crawl skipped because robots.txt disallows the crawler user-agent; continuing with allowed public URLs."
            )

        homepage: CrawledPage | None = None
        if homepage_allowed:
            homepage, homepage_elapsed = self._fetch_page(root_url, parser=parser, include_html=True)
            result.response_time_ms = homepage_elapsed
            if homepage is not None:
                result.homepage_status_code = homepage.status_code
                result.final_status_code = homepage.status_code
                result.redirect_count = int(homepage.headers.get("x-trmodule0-redirect-count", "0") or 0)
            if homepage is None:
                result.notes.append("Homepage fetch failed; continuing with sitemap and public URL fallback.")
            elif homepage.blocked_reason:
                result.blocked_reason = homepage.blocked_reason
                result.notes.append(
                    f"Homepage content ignored because the site returned a blocked/interstitial page: {homepage.blocked_reason}. Continuing with other public URLs."
                )
            else:
                result.homepage_html = homepage.html or ""
                result.homepage_headers = homepage.headers
                result.homepage_title = homepage.title
                result.meta_description = homepage.meta_description
                result.canonical_url = homepage.canonical_url
                result.language = homepage.language
                result.h1_count = homepage.h1_count
                result.word_count = homepage.word_count
                result.mobile_friendly = homepage.mobile_friendly
                result.indexable = homepage.indexable
                result.schema_types = homepage.schema_types
                result.social_profile_links = homepage.social_links
                result.observed_headings = homepage.headings[:18]
                result.navigation_labels = homepage.navigation_labels[:18]
                if homepage.generator:
                    result.generator_hints = [homepage.generator]
                result.framework_hints = homepage.framework_hints[:10]

        candidates = self._prioritize_candidates(
            root_url=root_url,
            homepage_links=homepage.discovered_links if homepage and not homepage.blocked_reason else [],
            sitemap_urls=sitemap_urls,
            excluded_pages=excluded_pages,
        )

        crawled_pages: list[CrawledPage] = []
        if homepage is not None and not homepage.blocked_reason:
            crawled_pages.append(homepage)
        seen_urls: set[str] = {normalized_root} if normalized_root else set()
        queue = deque(candidates)

        while queue and len(crawled_pages) < self.max_pages:
            target = queue.popleft()
            normalized = self._normalize_url(target)
            if not normalized or normalized in seen_urls:
                continue
            if parser and not parser.can_fetch(USER_AGENT, target):
                result.notes.append(f"Skipped {target} because robots.txt disallows it.")
                continue
            page, _elapsed = self._fetch_page(target, parser=parser, include_html=False)
            seen_urls.add(normalized)
            if page is None:
                continue
            if page.blocked_reason:
                result.notes.append(f"Skipped {target} because it returned blocked/interstitial content: {page.blocked_reason}.")
                continue
            crawled_pages.append(page)
            if result.final_status_code is None:
                result.final_status_code = page.status_code
            for link in page.discovered_links:
                link_normalized = self._normalize_url(link)
                if not link_normalized or link_normalized in seen_urls:
                    continue
                if self._should_skip_url(link, excluded_pages):
                    continue
                queue.append(link)

        result.crawled_pages = crawled_pages
        discovered_urls: list[str] = []
        seen_discovered: set[str] = set()
        for url in [*(page.url for page in crawled_pages), *sitemap_urls]:
            normalized = self._normalize_url(url)
            if not normalized or normalized in seen_discovered:
                continue
            seen_discovered.add(normalized)
            discovered_urls.append(normalized)
        result.discovered_urls = discovered_urls[:50]

        aggregated_pages = crawled_pages[:]
        if homepage is not None and not homepage.blocked_reason and homepage not in aggregated_pages:
            aggregated_pages.insert(0, homepage)

        if aggregated_pages:
            result.schema_types = sorted(
                {
                    schema
                    for page in aggregated_pages
                    for schema in page.schema_types
                    if schema
                }
            )[:12]
            result.social_profile_links = sorted(
                {
                    link
                    for page in aggregated_pages
                    for link in page.social_links
                    if link
                }
            )[:12]
            if not result.observed_headings:
                result.observed_headings = self._collect_text_signals(
                    [page.headings for page in aggregated_pages],
                    limit=24,
                )
            if not result.navigation_labels:
                result.navigation_labels = self._collect_text_signals(
                    [page.navigation_labels for page in aggregated_pages],
                    limit=24,
                )
            result.generator_hints = self._collect_text_signals(
                [[page.generator] for page in aggregated_pages if page.generator],
                limit=8,
            )
            result.framework_hints = self._collect_text_signals(
                [page.framework_hints for page in aggregated_pages],
                limit=12,
            )
            result.homepage_text_excerpt = self._build_content_summary(aggregated_pages)
            if not result.homepage_title and aggregated_pages[0].title:
                result.homepage_title = aggregated_pages[0].title
            if not result.meta_description and aggregated_pages[0].meta_description:
                result.meta_description = aggregated_pages[0].meta_description
            if not result.canonical_url and aggregated_pages[0].canonical_url:
                result.canonical_url = aggregated_pages[0].canonical_url
            if result.final_status_code is None:
                result.final_status_code = aggregated_pages[0].status_code
            if not result.language:
                result.language = aggregated_pages[0].language
            if not result.h1_count:
                result.h1_count = sum(page.h1_count for page in aggregated_pages[:3])
            if not result.word_count:
                result.word_count = sum(page.word_count for page in aggregated_pages[:3])
            if result.mobile_friendly is None:
                mobile_candidates = [page.mobile_friendly for page in aggregated_pages if page.mobile_friendly is not None]
                result.mobile_friendly = any(mobile_candidates) if mobile_candidates else None
            if result.indexable is None:
                indexable_candidates = [page.indexable for page in aggregated_pages if page.indexable is not None]
                result.indexable = any(indexable_candidates) if indexable_candidates else None
            result.broken_internal_links = self._check_broken_internal_links(
                parser=parser,
                crawled_pages=aggregated_pages,
            )
        result.notes.append(f"Crawled {len(crawled_pages)} HTML pages safely for Module 0 extraction.")
        return result

    def _load_robots(self, root_url: str) -> tuple[RobotFileParser | None, list[str]]:
        robots_url = urljoin(root_url.rstrip("/") + "/", "robots.txt")
        notes: list[str] = []
        text = self._fetch_text(robots_url)
        if text is None:
            notes.append("robots.txt could not be loaded for path-level crawl checks.")
            return None, notes
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(text.splitlines())
        notes.append("robots.txt was loaded for crawl allow/deny checks.")
        return parser, notes

    def _fetch_page(
        self,
        url: str,
        parser: RobotFileParser | None,
        include_html: bool,
    ) -> tuple[CrawledPage | None, int | None]:
        if parser and not parser.can_fetch(USER_AGENT, url):
            return (
                CrawledPage(
                    url=url,
                    page_type=self._page_type(url),
                    status_code=0,
                    blocked_reason="robots_disallow_url",
                ),
                None,
            )

        started = time.perf_counter()
        response = self._request("GET", url)
        elapsed = int((time.perf_counter() - started) * 1000)
        time.sleep(self.rate_limit_seconds)
        if response is None:
            return None, elapsed

        blocked_reason = self._blocked_reason(response.status_code, response.text)
        if blocked_reason:
            return (
                CrawledPage(
                    url=str(response.url),
                    page_type=self._page_type(str(response.url)),
                    status_code=response.status_code,
                    blocked_reason=blocked_reason,
                ),
                elapsed,
            )

        html = response.text
        if self.enable_playwright and self._should_try_playwright(html):
            rendered_html = self._try_playwright_render(str(response.url))
            if rendered_html:
                html = rendered_html

        page = self._extract_page(
            str(response.url),
            response.status_code,
            html,
            dict(response.headers),
            include_html=include_html,
        )
        if response.history:
            page.headers["x-trmodule0-redirect-count"] = str(len(response.history))
        return page, elapsed

    def _extract_page(
        self,
        url: str,
        status_code: int,
        html: str,
        headers: dict[str, str],
        include_html: bool,
    ) -> CrawledPage:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else None
        meta_tag = soup.find("meta", attrs={"name": "description"})
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        discovered_links = self._extract_links(url, soup)
        generator = self._extract_generator(soup)
        framework_hints = self._extract_framework_hints(soup, html)
        return CrawledPage(
            url=url,
            page_type=self._page_type(url),
            status_code=status_code,
            title=title,
            meta_description=meta_tag.get("content", "").strip() or None if meta_tag else None,
            canonical_url=canonical_tag.get("href", "").strip() or None if canonical_tag else None,
            text_excerpt=self._extract_text_excerpt(soup),
            language=self._extract_language(soup, headers),
            h1_count=len(soup.find_all("h1")),
            word_count=self._extract_word_count(soup),
            mobile_friendly=self._is_mobile_friendly(soup),
            indexable=self._is_indexable(soup, headers, status_code),
            schema_types=self._extract_schema_types(soup),
            social_links=self._extract_social_links(soup),
            headings=self._extract_headings(soup),
            navigation_labels=self._extract_navigation_labels(soup),
            generator=generator,
            framework_hints=framework_hints,
            discovered_links=discovered_links,
            headers={key.lower(): value for key, value in headers.items()},
            html=html if include_html else None,
        )

    def _extract_links(self, page_url: str, soup: BeautifulSoup) -> list[str]:
        base = urlparse(page_url)
        links: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or href.startswith(("mailto:", "tel:", "#", "javascript:")):
                continue
            absolute = urljoin(page_url, href)
            parsed = urlparse(absolute)
            if parsed.netloc != base.netloc:
                continue
            normalized = self._normalize_url(absolute)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            links.append(normalized)
            if len(links) >= self.max_links_per_page:
                break
        return links

    def _extract_text_excerpt(self, soup: BeautifulSoup) -> str | None:
        parts: list[str] = []
        for selector in ["h1", "h2", "p", "li"]:
            for element in soup.find_all(selector)[:18]:
                text = re.sub(r"\s+", " ", element.get_text(" ", strip=True))
                if not text or text in parts:
                    continue
                parts.append(text)
                if len(" ".join(parts)) >= 600:
                    return " ".join(parts)[:600].strip()
        return " ".join(parts)[:600].strip() if parts else None

    def _extract_word_count(self, soup: BeautifulSoup) -> int:
        text = soup.get_text(" ", strip=True)
        words = [token for token in re.split(r"\s+", text) if token]
        return len(words)

    def _extract_language(self, soup: BeautifulSoup, headers: dict[str, str]) -> str | None:
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            return html_tag.get("lang", "").strip().lower() or None
        content_language = headers.get("content-language") or headers.get("Content-Language")
        if content_language:
            return content_language.split(",")[0].strip().lower()
        return None

    def _is_mobile_friendly(self, soup: BeautifulSoup) -> bool | None:
        viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
        if viewport and viewport.get("content"):
            return True
        return None

    def _is_indexable(self, soup: BeautifulSoup, headers: dict[str, str], status_code: int) -> bool | None:
        if status_code >= 400:
            return False
        robots_meta = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
        robots_content = robots_meta.get("content", "").lower() if robots_meta else ""
        x_robots = (headers.get("x-robots-tag") or headers.get("X-Robots-Tag") or "").lower()
        if "noindex" in robots_content or "noindex" in x_robots:
            return False
        if status_code in {200, 201}:
            return True
        return None

    def _extract_schema_types(self, soup: BeautifulSoup) -> list[str]:
        types: list[str] = []
        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            text = tag.get_text(" ", strip=True)
            for schema in ["Organization", "LocalBusiness", "Article", "FAQPage", "HowTo", "Product", "Service", "BreadcrumbList"]:
                if schema.lower() in text.lower() and schema not in types:
                    types.append(schema)
        return types[:12]

    def _extract_social_links(self, soup: BeautifulSoup) -> list[str]:
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if any(domain in href for domain in ["linkedin.com", "facebook.com", "instagram.com", "youtube.com", "x.com"]):
                links.append(href)
        return sorted({item for item in links if item})[:12]

    def _extract_headings(self, soup: BeautifulSoup) -> list[str]:
        headings: list[str] = []
        seen: set[str] = set()
        for selector in ["h1", "h2", "h3"]:
            for element in soup.find_all(selector)[:18]:
                text = re.sub(r"\s+", " ", element.get_text(" ", strip=True))
                lowered = text.lower()
                if not text or lowered in seen:
                    continue
                seen.add(lowered)
                headings.append(text)
        return headings[:18]

    def _extract_navigation_labels(self, soup: BeautifulSoup) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()
        for container in soup.find_all(["nav", "header"])[:4]:
            for anchor in container.find_all("a", href=True)[:24]:
                text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
                lowered = text.lower()
                if not text or len(text.split()) > 4 or lowered in seen:
                    continue
                seen.add(lowered)
                labels.append(text)
        return labels[:24]

    def _extract_generator(self, soup: BeautifulSoup) -> str | None:
        generator = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
        if generator and generator.get("content"):
            return re.sub(r"\s+", " ", generator.get("content", "").strip())
        return None

    def _extract_framework_hints(self, soup: BeautifulSoup, html: str) -> list[str]:
        hints: list[str] = []
        html_lower = html.lower()
        if "__next_data__" in html_lower or "/_next/" in html_lower:
            hints.append("nextjs")
        if "__nuxt" in html_lower or "/_nuxt/" in html_lower:
            hints.append("nuxt")
        if "data-reactroot" in html_lower or "react" in html_lower and "react-dom" in html_lower:
            hints.append("react")
        if "ng-version" in html_lower or "<app-root" in html_lower:
            hints.append("angular")
        if "data-v-app" in html_lower or "vue.js" in html_lower:
            hints.append("vue")
        for script in soup.find_all("script", src=True)[:20]:
            src = script.get("src", "").lower()
            if "shopify" in src:
                hints.append("shopify")
            if "wix" in src:
                hints.append("wix")
            if "webflow" in src:
                hints.append("webflow")
        return sorted({hint for hint in hints if hint})

    def _build_content_summary(self, pages: list[CrawledPage]) -> str | None:
        ranked = sorted(
            pages,
            key=lambda page: (
                {"homepage": 0, "service": 1, "category_product": 2, "location": 3, "about_contact": 4, "blog": 5}.get(page.page_type, 6),
                len(page.text_excerpt or ""),
            ),
            reverse=False,
        )
        chunks: list[str] = []
        seen: set[str] = set()
        for page in ranked[:8]:
            for part in [page.title or "", page.text_excerpt or ""]:
                cleaned = re.sub(r"\s+", " ", part).strip()
                if not cleaned or cleaned.lower() in seen:
                    continue
                seen.add(cleaned.lower())
                chunks.append(cleaned)
            if len(" ".join(chunks)) >= 900:
                break
        summary = " ".join(chunks).strip()
        return summary[:900] if summary else None

    def _collect_text_signals(self, groups: list[list[str]], limit: int) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                cleaned = re.sub(r"\s+", " ", item).strip()
                lowered = cleaned.lower()
                if not cleaned or lowered in seen:
                    continue
                seen.add(lowered)
                values.append(cleaned)
                if len(values) >= limit:
                    return values
        return values

    def _check_broken_internal_links(
        self,
        parser: RobotFileParser | None,
        crawled_pages: list[CrawledPage],
        max_checks: int = 6,
    ) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for page in crawled_pages[:4]:
            for link in page.discovered_links[:8]:
                normalized = self._normalize_url(link)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                candidates.append(normalized)
                if len(candidates) >= max_checks:
                    break
            if len(candidates) >= max_checks:
                break

        broken: list[str] = []
        for link in candidates:
            if parser and not parser.can_fetch(USER_AGENT, link):
                continue
            response = self._request("HEAD", link)
            if response is None or response.status_code >= 400:
                response = self._request("GET", link)
            if response is None or response.status_code >= 400:
                broken.append(link)
        return broken[:max_checks]

    def _prioritize_candidates(
        self,
        root_url: str,
        homepage_links: list[str],
        sitemap_urls: list[str],
        excluded_pages: list[str],
    ) -> list[str]:
        combined = [*homepage_links, *sitemap_urls]
        candidates: list[tuple[int, str]] = []
        seen: set[str] = set()
        for url in combined:
            normalized = self._normalize_url(url)
            if not normalized or normalized == self._normalize_url(root_url) or normalized in seen:
                continue
            seen.add(normalized)
            if self._should_skip_url(normalized, excluded_pages):
                continue
            candidates.append((self._priority_score(normalized), normalized))
        candidates.sort(key=lambda item: (item[0], item[1]))
        return [url for _score, url in candidates]

    def _priority_score(self, url: str) -> int:
        lowered = url.lower()
        if lowered.rstrip("/") == lowered.split("//", 1)[0] + "//" + urlparse(lowered).netloc:
            return 0
        if any(token in lowered for token in ["service", "services", "repair", "replacement", "installation"]):
            return 1
        if any(token in lowered for token in ["category", "categories", "product", "products", "collection", "collections", "furniture", "chair", "table", "bed"]):
            return 2
        if any(token in lowered for token in ["location", "locations", "melbourne", "sydney", "brisbane", "perth", "adelaide"]):
            return 3
        if any(token in lowered for token in ["about", "contact", "company", "showroom"]):
            return 4
        if any(token in lowered for token in ["blog", "news", "article", "resource", "guide"]):
            return 5
        return 6

    def _page_type(self, url: str) -> str:
        lowered = url.lower()
        if lowered.rstrip("/").count("/") <= 2:
            return "homepage"
        if any(token in lowered for token in ["service", "services", "repair", "replacement", "installation"]):
            return "service"
        if any(token in lowered for token in ["category", "categories", "product", "products", "collection", "collections", "furniture", "chair", "table", "bed"]):
            return "category_product"
        if any(token in lowered for token in ["location", "locations", "melbourne", "sydney", "brisbane", "perth", "adelaide"]):
            return "location"
        if any(token in lowered for token in ["about", "contact", "company", "showroom"]):
            return "about_contact"
        if any(token in lowered for token in ["blog", "news", "article", "resource", "guide"]):
            return "blog"
        return "general"

    def _should_skip_url(self, url: str, excluded_pages: list[str]) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in IRRELEVANT_EXTENSIONS):
            return True
        if any(fragment in path for fragment in ["/cart", "/checkout", "/login", "/account", "/search", "/wp-admin", "/cdn-cgi/"]):
            return True
        if any(excluded and excluded in path for excluded in excluded_pages):
            return True
        return False

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        normalized = normalized.rstrip("/")
        return normalized or url

    def _blocked_reason(self, status_code: int, body: str) -> str | None:
        lowered = (body or "").lower()
        if status_code in {401, 403}:
            return f"http_{status_code}_blocked"
        if status_code == 429:
            return "http_429_rate_limited"
        if any(marker in lowered for marker in BLOCKED_MARKERS):
            return "anti_bot_interstitial"
        return None

    def _should_try_playwright(self, html: str) -> bool:
        lowered = html.lower()
        if not lowered:
            return False
        low_text_shell = len(re.sub(r"\s+", " ", lowered).strip()) < 1200
        js_markers = [
            "enable javascript",
            "__next",
            "__nuxt",
            "application/json",
            "data-reactroot",
            "ng-version",
            "id=\"app\"",
            "id=\"root\"",
        ]
        return bool(low_text_shell and any(token in lowered for token in js_markers))

    def _try_playwright_render(self, url: str) -> str | None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return None

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, wait_until="domcontentloaded", timeout=int(self.request_timeout * 1000))
                page.wait_for_timeout(1200)
                content = page.content()
                browser.close()
                if self._blocked_reason(200, content):
                    return None
                return content
        except Exception:
            return None

    def _fetch_text(self, url: str) -> str | None:
        response = self._request("GET", url)
        if response is None or response.status_code >= 400:
            return None
        return response.text

    def _request(self, method: str, url: str):
        if requests is not None and self._requests_cached_session is not None:
            try:
                response = self._requests_cached_session.request(
                    method,
                    url,
                    timeout=self.request_timeout,
                    allow_redirects=True,
                    headers={"User-Agent": USER_AGENT, "Accept-Language": "en-AU,en;q=0.9"},
                )
                return response
            except requests.RequestException:
                return None

        try:
            with httpx.Client(timeout=httpx.Timeout(self.request_timeout, connect=min(self.request_timeout, 6.0))) as client:
                return client.request(
                    method,
                    url,
                    follow_redirects=True,
                    headers={"User-Agent": USER_AGENT, "Accept-Language": "en-AU,en;q=0.9"},
                )
        except httpx.HTTPError:
            return None

    def _build_requests_session(self):
        session = requests.Session()
        if Retry is not None and HTTPAdapter is not None:
            retries = Retry(
                total=2,
                backoff_factor=0.6,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods={"GET", "HEAD"},
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retries)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
        return session

    def _env_int(self, key: str, default: int) -> int:
        try:
            value = int((os.getenv(key) or "").strip())
        except ValueError:
            return default
        return value if value > 0 else default

    def _env_float(self, key: str, default: float) -> float:
        try:
            value = float((os.getenv(key) or "").strip())
        except ValueError:
            return default
        return value if value > 0 else default
