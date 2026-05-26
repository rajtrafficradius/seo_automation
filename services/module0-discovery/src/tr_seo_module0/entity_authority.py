from __future__ import annotations

from tr_seo_contracts.module0 import EntityAuthorityBaseline, EntityMention


class EntityAuthorityService:
    def build(
        self,
        brand_name: str,
        brand_profiles: list[str],
        social_profile_links: list[str],
        detected_schema_types: list[str],
    ) -> EntityAuthorityBaseline:
        same_as_links = sorted({*brand_profiles, *social_profile_links})
        score = 15
        consistency_gaps: list[str] = []
        reinforcement_opportunities: list[str] = []
        mentions: list[EntityMention] = []

        if same_as_links:
            score += min(25, len(same_as_links) * 5)
            for link in same_as_links:
                mentions.append(
                    EntityMention(
                        source_name=self._source_name(link),
                        source_url=link,
                        mention_type="profile",
                        consistent=True,
                    )
                )
        else:
            consistency_gaps.append("No sameAs or external brand profile links were detected.")
            reinforcement_opportunities.append("Add consistent brand profile links across key directories and socials.")
            mentions.append(
                EntityMention(
                    source_name=brand_name or "Brand",
                    source_url=None,
                    mention_type="brand_reference",
                    consistent=True,
                )
            )

        if any(schema.lower() in {"organization", "localbusiness"} for schema in detected_schema_types):
            score += 20
            mentions.append(
                EntityMention(
                    source_name="On-site structured data",
                    source_url=None,
                    mention_type="schema",
                    consistent=True,
                )
            )
        else:
            consistency_gaps.append("Organization-level structured data was not clearly detected on the site.")
            reinforcement_opportunities.append("Deploy Organization/LocalBusiness schema with sameAs links.")

        if len(same_as_links) < 3:
            consistency_gaps.append("Entity footprint across third-party sources looks thin.")
            reinforcement_opportunities.append("Secure more corroborating brand profiles and editorial mentions.")
        else:
            score += 15

        if brand_name and len(brand_name.split()) >= 2:
            score += 10
        else:
            consistency_gaps.append("Brand naming may be too generic for clean entity disambiguation.")
            reinforcement_opportunities.append("Strengthen brand disambiguation in schema and profile descriptions.")

        if not reinforcement_opportunities:
            reinforcement_opportunities.extend(
                [
                    "Expand corroborating citations across industry directories and trusted profiles.",
                    "Add richer brand/about content that reinforces entity relationships and service coverage.",
                ]
            )
        if not consistency_gaps:
            consistency_gaps.append("Entity signals are present, but ongoing consistency monitoring is still recommended.")

        score = min(score, 100)
        return EntityAuthorityBaseline(
            score=score,
            knowledge_panel_status=self._knowledge_panel_status(score, same_as_links, detected_schema_types),
            same_as_links=same_as_links,
            brand_mentions=mentions,
            consistency_gaps=consistency_gaps,
            reinforcement_opportunities=reinforcement_opportunities,
            methodology="Entity baseline derived from detected schema, sameAs links, and supplied brand profiles.",
        )

    def _knowledge_panel_status(
        self,
        score: int,
        same_as_links: list[str],
        detected_schema_types: list[str],
    ) -> str:
        if score >= 70 and same_as_links and any(
            schema.lower() in {"organization", "localbusiness"} for schema in detected_schema_types
        ):
            return "likely_entity_eligible_unverified"
        if same_as_links:
            return "entity_footprint_present_unverified"
        return "entity_visibility_low_unverified"

    def _source_name(self, link: str) -> str:
        if "linkedin" in link:
            return "LinkedIn"
        if "facebook" in link:
            return "Facebook"
        if "instagram" in link:
            return "Instagram"
        if "youtube" in link:
            return "YouTube"
        return link.split("//")[-1].split("/")[0]
