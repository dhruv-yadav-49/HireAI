"""
app/services/marketplace_service.py

High-level business service for Agent Marketplace Platform.
Coordinates packages, validation pipelines, compatibility checking, tenant installations, and event bus notifications.
"""
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.security_context import SecurityContext
from app.models.marketplace_package import MarketplacePackage
from app.models.agent_installation import AgentInstallation
from app.models.agent_compatibility_log import AgentCompatibilityLog
from app.models.enums import AgentLifecycleStatus, AgentInstallationStatus, AgentPackageType
from app.repositories.marketplace_repository import MarketplaceRepository

from app.marketplace.package_builder import AgentPackage
from app.marketplace.manifest_parser import AgentManifestParser
from app.marketplace.compatibility_checker import AgentCompatibilityChecker
from app.marketplace.validation_pipeline import MarketplaceValidationPipeline
from app.marketplace.marketplace_installer import MarketplaceInstaller
from app.marketplace.marketplace_registry import MarketplaceRegistry
from app.marketplace.marketplace_metrics import MarketplaceMetricsService, MarketplaceMetricsSummary


class MarketplaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MarketplaceRepository(db)
        self.pipeline = MarketplaceValidationPipeline()
        self.registry = MarketplaceRegistry()

    async def upload_package(
        self,
        raw_manifest_yaml: str,
        author: str = "Official Platform",
        package_type: AgentPackageType = AgentPackageType.COMMUNITY,
    ) -> MarketplacePackage:
        """Uploads a raw .hireagent package manifest (CTO #1, #2)."""
        pkg_artifact = AgentPackage.from_manifest_yaml(raw_manifest_yaml, publisher_id=author)
        manifest = pkg_artifact.manifest

        existing = await self.repo.get_package_by_name(manifest.name)
        if existing:
            # Update existing
            existing.version = manifest.version
            existing.manifest_yaml = raw_manifest_yaml
            existing.manifest_json = manifest.model_dump()
            existing.package_hash = pkg_artifact.package_hash
            existing.latest_version = manifest.version
            existing.lifecycle_status = AgentLifecycleStatus.DRAFT
            await self.db.commit()
            return existing

        db_package = MarketplacePackage(
            package_name=manifest.name,
            display_name=manifest.display_name,
            description=manifest.description,
            author=author,
            package_type=package_type,
            version=manifest.version,
            manifest_version=manifest.manifest_version,
            api_version=manifest.api_version,
            sdk_version=manifest.sdk_version,
            runtime_requirement=manifest.runtime,
            latest_version=manifest.version,
            manifest_yaml=raw_manifest_yaml,
            manifest_json=manifest.model_dump(),
            package_hash=pkg_artifact.package_hash,
            publisher_id=author,
            lifecycle_status=AgentLifecycleStatus.DRAFT,
        )
        saved = await self.repo.create_package(db_package)
        await self.db.commit()
        return saved

    async def validate_package(self, package_id: uuid.UUID) -> Dict[str, Any]:
        """Executes explicit 6-stage validation pipeline on package (CTO #5)."""
        pkg = await self.repo.get_package_by_id(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        artifact = AgentPackage.from_manifest_yaml(pkg.manifest_yaml, publisher_id=pkg.author)
        res = self.pipeline.run_pipeline(artifact)

        pkg.lifecycle_status = res.final_lifecycle_status
        pkg.validation_results_json = {
            "overall_passed": res.overall_passed,
            "stages": [
                {
                    "stage_name": s.stage_name,
                    "passed": s.passed,
                    "message": s.message,
                    "details": s.details,
                }
                for s in res.stage_results
            ],
        }

        if res.overall_passed:
            self.registry.register_package(artifact)
            pkg.stable_version = pkg.version

        await self.db.commit()
        return pkg.validation_results_json

    async def check_compatibility(
        self, sec_ctx: SecurityContext, package_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Validates compatibility against tenant capabilities (CTO #4, #10)."""
        pkg = await self.repo.get_package_by_id(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        manifest = AgentManifestParser.parse_dict(pkg.manifest_json)
        checker = AgentCompatibilityChecker()
        res = checker.check_compatibility(manifest)

        # Log audit entry
        log_entry = AgentCompatibilityLog(
            organization_id=sec_ctx.organization_id,
            package_id=pkg.id,
            agent_key=pkg.package_name,
            compatible=res.compatible,
            check_type="FULL_COMPATIBILITY",
            details_json=res.details,
        )
        await self.repo.log_compatibility_check(log_entry)
        await self.db.commit()
        return res.details

    async def install_package(
        self, sec_ctx: SecurityContext, package_id: uuid.UUID
    ) -> AgentInstallation:
        """Installs and verifies agent package into active tenant (CTO #7, #8, #11)."""
        pkg = await self.repo.get_package_by_id(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        artifact = AgentPackage.from_manifest_yaml(pkg.manifest_yaml, publisher_id=pkg.author)
        existing = await self.repo.get_installation(sec_ctx.organization_id, package_id)

        previous_ver = existing.current_version if existing else None
        install_res = MarketplaceInstaller.install_and_verify(
            org_id=sec_ctx.organization_id,
            package=artifact,
            previous_version=previous_ver,
        )

        if existing:
            existing.previous_version = previous_ver
            existing.current_version = pkg.version
            existing.status = install_res["status"]
            existing.verification_results_json = install_res
            await self.db.commit()
            return existing

        inst = AgentInstallation(
            organization_id=sec_ctx.organization_id,
            package_id=pkg.id,
            agent_key=pkg.package_name,
            current_version=pkg.version,
            previous_version=None,
            installed_by=sec_ctx.user_id,
            status=install_res["status"],
            verification_results_json=install_res,
        )
        saved = await self.repo.create_installation(inst)
        await self.db.commit()
        return saved

    async def rollback_installation(
        self, sec_ctx: SecurityContext, installation_id: uuid.UUID
    ) -> AgentInstallation:
        """Rolls back tenant agent installation to previous version (CTO #8)."""
        stmt = select(AgentInstallation).where(
            AgentInstallation.id == installation_id,
            AgentInstallation.organization_id == sec_ctx.organization_id,
        )
        res = await self.db.execute(stmt)
        inst = res.scalar_one_or_none()
        if not inst or not inst.previous_version:
            raise ValueError("No previous version available to roll back.")

        rb_res = MarketplaceInstaller.rollback(
            org_id=sec_ctx.organization_id,
            agent_key=inst.agent_key,
            current_version=inst.current_version,
            previous_version=inst.previous_version,
        )

        inst.current_version = inst.previous_version
        inst.previous_version = None
        inst.status = AgentInstallationStatus.ACTIVE
        inst.verification_results_json = rb_res
        await self.db.commit()
        return inst
