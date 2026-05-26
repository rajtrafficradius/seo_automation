from __future__ import annotations

from sqlalchemy.orm import Session

from tr_seo_contracts.module0 import Module0Response
from tr_seo_db.models import DiscoveryData, Module0Run, Project


class Module0Repository:
    def save_run(
        self,
        session: Session,
        response: Module0Response,
        cdd_storage_path: str,
    ) -> tuple[Project, Module0Run, DiscoveryData]:
        project = (
            session.query(Project)
            .filter(Project.domain == response.site_classification.detected_domain)
            .one_or_none()
        )
        if project is None:
            project = Project(
                website_url=str(response.request.website_url),
                domain=response.site_classification.detected_domain,
                target_country=response.request.target_country,
                brand_name=response.request.brand_name,
                business_type=response.site_classification.business_type.value,
            )
            session.add(project)
            session.flush()

        module0_run = Module0Run(
            project_id=project.id,
            status="completed",
            semrush_status=response.semrush.status,
            semrush_data_source=response.semrush.data_source,
            fallback_used=response.semrush.fallback_used,
            cdd_filename=response.cdd_file.filename,
            cdd_content_type=response.cdd_file.content_type,
            cdd_storage_path=cdd_storage_path,
        )
        session.add(module0_run)
        session.flush()

        discovery = DiscoveryData(
            module0_run_id=module0_run.id,
            tam_estimate=response.tam_estimate,
            request_payload=response.request.model_dump(mode="json"),
            cdd_extraction=response.cdd_extraction.model_dump(mode="json"),
            site_classification=response.site_classification.model_dump(mode="json"),
            website_profile=response.website_profile.model_dump(mode="json"),
            semrush_snapshot=response.semrush.model_dump(mode="json"),
            competitive_intelligence=response.competitive_intelligence.model_dump(mode="json"),
            master_keyword_universe=[item.model_dump(mode="json") for item in response.master_keyword_universe],
            keyword_clusters=[item.model_dump(mode="json") for item in response.keyword_clusters],
            quick_wins=response.quick_wins.model_dump(mode="json"),
            tam_dataset=response.tam_dataset.model_dump(mode="json"),
            url_architecture_map=[item.model_dump(mode="json") for item in response.url_architecture_map],
            minimum_effort_points=[item.model_dump(mode="json") for item in response.minimum_effort_points],
            ai_sov_baseline=response.ai_sov_baseline.model_dump(mode="json"),
            fan_out_map=response.fan_out_map.model_dump(mode="json"),
            entity_authority_baseline=response.entity_authority_baseline.model_dump(mode="json"),
            exports=response.exports.model_dump(mode="json"),
            warnings_errors=[item.model_dump(mode="json") for item in response.warnings_errors],
            run_timestamps=response.run_timestamps.model_dump(mode="json"),
            notes="\n".join(response.next_steps) if response.next_steps else None,
        )
        session.add(discovery)
        session.commit()
        session.refresh(project)
        session.refresh(module0_run)
        session.refresh(discovery)
        return project, module0_run, discovery
