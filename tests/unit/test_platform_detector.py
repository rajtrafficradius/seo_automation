from tr_seo_module0.platform_detector import PlatformDetector


def test_platform_detector_fingerprints_nextjs_catalog_stack() -> None:
    detector = PlatformDetector()

    result = detector.detect(
        html="""
        <html lang="en">
          <head>
            <script id="__NEXT_DATA__">{}</script>
          </head>
          <body>
            <nav><a href="/collections/healthcare-furniture">Healthcare Furniture</a></nav>
          </body>
        </html>
        """,
        headers={"server": "nginx"},
        sample_urls=[
            "https://example.com/collections/healthcare-furniture",
            "https://example.com/collections/commercial-furniture",
        ],
        sample_titles=["Healthcare Furniture | Example"],
        schema_types=["Organization", "Product"],
        navigation_labels=["Healthcare Furniture", "Commercial Furniture", "Resources"],
        framework_hints=["nextjs"],
        generator_hints=["Next.js"],
    )

    assert result["cms"] in {"nextjs_custom_stack", "shopify"}
    assert result["framework"] == "nextjs"
    assert "category_product_model" in result["active_components"]
    assert "content_hub" in result["active_components"]
