from __future__ import annotations

from tr_seo_contracts.module0 import KeywordIntent, KeywordPriority


class IntentClassifier:
    TRANSACTIONAL_TOKENS = {
        "buy",
        "cost",
        "quote",
        "price",
        "prices",
        "hire",
        "company",
        "service",
        "repair",
        "replacement",
        "install",
        "installation",
        "near me",
    }
    NAVIGATIONAL_TOKENS = {
        "brand",
        "reviews",
        "contact",
        "phone",
        "opening hours",
        "how to choose",
        "best",
    }

    def classify(self, keyword: str, brand_terms: set[str]) -> tuple[KeywordIntent, KeywordPriority]:
        lowered = keyword.lower().strip()
        tokens = set(lowered.split())

        if brand_terms and tokens.intersection(brand_terms):
            return KeywordIntent.NAVIGATIONAL_AEO, KeywordPriority.P2
        if any(token in lowered for token in self.TRANSACTIONAL_TOKENS):
            return KeywordIntent.TRANSACTIONAL, KeywordPriority.P1
        if any(token in lowered for token in self.NAVIGATIONAL_TOKENS):
            return KeywordIntent.NAVIGATIONAL_AEO, KeywordPriority.P2
        return KeywordIntent.INFORMATIONAL, KeywordPriority.P3
