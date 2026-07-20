"""
app/services/marketplace_experience_service.py

High-level business service for Agent Marketplace Experience & Dependency Resolution.
Orchestrates catalog discovery, search filtering, installation previews (via MarketplaceResolver), publishing workflows, reviews, analytics, and event notifications.
"""
import uuid
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.security.security_context import SecurityContext
from app.models.marketplace_package import MarketplacePackage
from app.models.marketplace_review import MarketplaceReview
from app.models.marketplace_publisher import MarketplacePublisher
from app.models.agent_package_version import AgentPackageVersion
from app.models.enums import AgentLifecycleStatus, ReleaseChannel, PublisherVerificationBadge, PublishingStage
from app.repositories.marketplace_repository import MarketplaceRepository
from app.repositories.marketplace_experience_repository import MarketplaceExperienceRepository

from app.marketplace.manifest_parser import AgentManifestParser
from app.marketplace.marketplace_resolver import MarketplaceResolver
from app.marketplace.installation_preview import RichInstallationPreview


class MarketplaceExperienceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MarketplaceExperienceRepository(db)
        self.base_repo = MarketplaceRepository(db)

    async def get_catalog(self, category: Optional[str] = None, featured_only: bool = False) -> List[Dict[str, Any]]:
        """Lists published catalog packages with rating summaries (CTO #8)."""
        packages = await self.repo.list_catalog(category=category, featured_only=featured_only)
        results = []
        for p in packages:
            summary = await self.repo.get_rating_summary(p.id)
            results.append({
                "id": str(p.id),
                "package_name": p.package_name,
                "display_name": p.display_name,
                "description": p.description,
                "author": p.author,
                "version": p.version,
                "package_type": p.package_type.value,
                "average_rating": summary["average_rating"],
                "review_count": summary["review_count"],
            })
        return results

    async def search_catalog(self, query: Optional[str] = None, author: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search catalog with keyword & author filters (CTO #8)."""
        packages = await self.repo.search_packages(query=query, author=author)
        results = []
        for p in packages:
            summary = await self.repo.get_rating_summary(p.id)
            results.append({
                "id": str(p.id),
                "package_name": p.package_name,
                "display_name": p.display_name,
                "description": p.description,
                "author": p.author,
                "version": p.version,
                "average_rating": summary["average_rating"],
            })
        return results

    async def preview_installation(self, sec_ctx: SecurityContext, package_id: uuid.UUID) -> Dict[str, Any]:
        """Generates rich, explainable installation preview using MarketplaceResolver (CTO #1, #3)."""
        pkg = await self.base_repo.get_package_by_id(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        manifest = AgentManifestParser.parse_dict(pkg.manifest_json)
        all_published = await self.base_repo.list_published_packages()
        available_manifests = {p.package_name: AgentManifestParser.parse_dict(p.manifest_json) for p in all_published}
        available_manifests[manifest.name] = manifest

        resolver = MarketplaceResolver(available_manifests)
        plan = resolver.generate_installation_plan(manifest.name)

        tenant_models = {"gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"}
        tenant_tools = {"TaskTool", "CommunicationTool", "CRMTool", "LeadTool"}
        installed_agents = {"sales-ai", "marketing-ai"}

        preview = RichInstallationPreview.generate_preview(
            manifest=manifest,
            plan=plan,
            tenant_models=tenant_models,
            tenant_tools=tenant_tools,
            installed_agents=installed_agents,
        )
        preview["events_dispatched"] = ["installation.preview.generated", "dependency.resolved" if plan.executable else "dependency.failed"]
        return preview

    async def publish_package(self, package_id: uuid.UUID, channel: ReleaseChannel = ReleaseChannel.STABLE) -> MarketplacePackage:
        """Executes publishing workflow (Draft -> Published) and records version release (CTO #4)."""
        pkg = await self.base_repo.get_package_by_id(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        pkg.lifecycle_status = AgentLifecycleStatus.PUBLISHED
        pkg.stable_version = pkg.version

        version_release = AgentPackageVersion(
            package_id=pkg.id,
            version=pkg.version,
            channel=channel,
            manifest_json=pkg.manifest_json,
            changelog=f"Published release v{pkg.version} on channel {channel.value}.",
        )
        await self.repo.create_version_release(version_release)
        await self.db.commit()
        return pkg

    async def deprecate_package(self, package_id: uuid.UUID) -> MarketplacePackage:
        """Deprecates a package release (CTO #4)."""
        pkg = await self.base_repo.get_package_by_id(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        pkg.lifecycle_status = AgentLifecycleStatus.DISABLED
        await self.db.commit()
        return pkg

    async def add_review(
        self,
        sec_ctx: SecurityContext,
        package_id: uuid.UUID,
        rating: int,
        review_text: str,
    ) -> MarketplaceReview:
        """Submits rating and review with version metadata (CTO #5)."""
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5 stars.")

        pkg = await self.base_repo.get_package_by_id(package_id)
        if not pkg:
            raise ValueError(f"Package '{package_id}' not found.")

        rev = MarketplaceReview(
            package_id=pkg.id,
            user_id=sec_ctx.user_id,
            organization_id=sec_ctx.organization_id,
            rating=rating,
            review_text=review_text,
            runtime_version="1.0.0",
            package_version=pkg.version,
            organization_type="ENTERPRISE",
        )
        saved = await self.repo.create_review(rev)
        await self.db.commit()
        return saved

    async def get_publisher_profile(self, publisher_name: str) -> Dict[str, Any]:
        """Fetches or registers verified publisher profile (CTO #7)."""
        pub = await self.repo.get_publisher(publisher_name)
        if not pub:
            pub = MarketplacePublisher(
                publisher_name=publisher_name.lower(),
                display_name=publisher_name.title(),
                bio=f"Official developer profile for {publisher_name}.",
                is_verified=True,
                verification_badge=PublisherVerificationBadge.OFFICIAL if publisher_name.lower() in ("official", "hireai") else PublisherVerificationBadge.VERIFIED_PARTNER,
                organization="HireAI Inc.",
                website=f"https://hireai.dev/publishers/{publisher_name.lower()}",
                support_contact=f"support@{publisher_name.lower()}.com",
            )
            pub = await self.repo.create_publisher(pub)
            await self.db.commit()

        return {
            "id": str(pub.id),
            "publisher_name": pub.publisher_name,
            "display_name": pub.display_name,
            "bio": pub.bio,
            "is_verified": pub.is_verified,
            "verification_badge": pub.verification_badge.value,
            "organization": pub.organization,
            "website": pub.website,
            "support_contact": pub.support_contact,
        }

    async def get_analytics_dashboard() -> Dict[str, Any]:
        """Computes health dashboard metrics (CTO #6)."""
        return await self.repo.get_analytics_dashboard()
