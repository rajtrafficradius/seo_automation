from __future__ import annotations

import re


class PlatformDetector:
    def detect(
        self,
        html: str,
        headers: dict[str, str],
        *,
        sample_urls: list[str] | None = None,
        sample_titles: list[str] | None = None,
        schema_types: list[str] | None = None,
        navigation_labels: list[str] | None = None,
        framework_hints: list[str] | None = None,
        generator_hints: list[str] | None = None,
    ) -> dict[str, str | list[str] | None]:
        html_lower = html.lower()
        header_blob = " ".join(f"{key}:{value}" for key, value in headers.items()).lower()
        url_blob = " ".join(sample_urls or []).lower()
        title_blob = " ".join(sample_titles or []).lower()
        schema_blob = " ".join(schema_types or []).lower()
        nav_blob = " ".join(navigation_labels or []).lower()
        framework_blob = " ".join(framework_hints or []).lower()
        generator_blob = " ".join(generator_hints or []).lower()
        signal_blob = " ".join(
            [
                html_lower,
                header_blob,
                url_blob,
                title_blob,
                schema_blob,
                nav_blob,
                framework_blob,
                generator_blob,
            ]
        )

        cms = "unknown"
        cms_version: str | None = None
        page_builder: str | None = None
        active_components: list[str] = []
        theme_or_template: str | None = None
        framework: str | None = None

        generator_match = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', html, re.I)
        generator = generator_match.group(1).strip() if generator_match else ""
        lowered_generator = generator.lower()

        if any(token in signal_blob for token in ["wordpress", "/wp-content/", "wp-json", "wp-includes"]):
            cms = "wordpress"
            cms_version = self._extract_version(lowered_generator, "wordpress")
            active_components.extend(self._extract_wp_components(html, "plugins"))
            theme_match = re.search(r"/wp-content/themes/([^/]+)/", html_lower)
            if theme_match:
                theme_or_template = theme_match.group(1)
                active_components.append(theme_or_template)
        elif any(token in signal_blob for token in ["shopify", "cdn.shopify.com", "myshopify.com", "shopify.theme", "/collections/", "/products/"]):
            cms = "shopify"
            active_components.extend(["shopify_catalog", "shopify_theme"])
        elif any(token in signal_blob for token in ["wix", "wixstatic.com", "wix-image", "wixsite", "thunderbolt"]):
            cms = "wix"
            active_components.append("wix_site_builder")
        elif any(token in signal_blob for token in ["squarespace", "static.squarespace.com", "squarespace-cdn"]):
            cms = "squarespace"
        elif any(token in signal_blob for token in ["webflow", "w-webflow", "data-wf-domain", "webflow.io"]):
            cms = "webflow"
            active_components.append("webflow_designer")
        elif any(token in signal_blob for token in ["hubspot", "hs-scripts.com", "hsforms", "hubspotusercontent"]):
            cms = "hubspot"
        elif any(token in signal_blob for token in ["drupal", "drupal-settings-json", "sites/default/files"]):
            cms = "drupal"
        elif any(token in signal_blob for token in ["joomla", "com_content", "option=com_"]):
            cms = "joomla"
        elif any(token in signal_blob for token in ["craft cms", "craftcms", "/cpresources/"]):
            cms = "craftcms"
        elif any(token in signal_blob for token in ["bigcommerce", "cdn11.bigcommerce.com"]):
            cms = "bigcommerce"

        if "elementor" in html_lower:
            page_builder = "elementor"
            active_components.append("elementor")
        elif "wpbakery" in html_lower or "js_composer" in html_lower:
            page_builder = "wpbakery"
            active_components.append("wpbakery")
        elif "divi" in html_lower:
            page_builder = "divi"
            active_components.append("divi")
        elif "oxygen" in html_lower:
            page_builder = "oxygen"
            active_components.append("oxygen")
        elif "beaver builder" in html_lower or "fl-builder" in html_lower:
            page_builder = "beaver_builder"
            active_components.append("beaver_builder")

        if any(token in signal_blob for token in ["__next_data__", "/_next/", "nextjs", "next.js"]):
            framework = "nextjs"
        elif any(token in signal_blob for token in ["__nuxt", "/_nuxt/", "nuxt"]):
            framework = "nuxt"
        elif any(token in signal_blob for token in ["data-reactroot", "react", "react-dom", "/static/js/main."]):
            framework = "react"
        elif any(token in signal_blob for token in ["ng-version", "angular", "<app-root"]):
            framework = "angular"
        elif any(token in signal_blob for token in ["data-v-app", "vue", "vue.js"]):
            framework = "vue"

        if framework:
            active_components.append(framework)
            if not page_builder:
                page_builder = f"{framework}_frontend"

        if cms == "unknown" and "x-powered-by" in header_blob:
            powered_by = headers.get("x-powered-by", "")
            if powered_by:
                cms = powered_by.lower()

        if cms == "unknown" and framework:
            cms = f"{framework}_custom_stack"

        if any(token in signal_blob for token in ["faqpage", "faq", "frequently asked"]):
            active_components.append("faq_content")
        if any(token in signal_blob for token in ["article", "blog", "resource", "guide"]):
            active_components.append("content_hub")
        if any(token in signal_blob for token in ["localbusiness", "location", "locations", "showroom"]):
            active_components.append("location_pages")
        if any(token in signal_blob for token in ["service", "services", "repair", "replacement", "installation"]):
            active_components.append("service_content_model")
        if any(token in signal_blob for token in ["product", "products", "collection", "collections", "category", "categories"]):
            active_components.append("category_product_model")
        if any(token in signal_blob for token in ["about", "contact", "team", "showroom"]):
            active_components.append("trust_pages")

        return {
            "cms": cms or "unknown",
            "cms_version": cms_version,
            "page_builder": page_builder,
            "active_components": sorted({item for item in active_components if item}),
            "theme_or_template": theme_or_template,
            "framework": framework,
            "fingerprints": sorted(
                {
                    item
                    for item in [
                        cms if cms != "unknown" else None,
                        framework,
                        theme_or_template,
                        page_builder,
                        *active_components,
                    ]
                    if item
                }
            ),
        }

    def _extract_wp_components(self, html: str, component_type: str) -> list[str]:
        pattern = re.compile(rf"/wp-content/{component_type}/([^/]+)/", re.I)
        return sorted({match.group(1).lower() for match in pattern.finditer(html)})

    def _extract_version(self, text: str, product: str) -> str | None:
        match = re.search(rf"{product}\s*([0-9][0-9.\-a-z]*)", text)
        return match.group(1) if match else None
