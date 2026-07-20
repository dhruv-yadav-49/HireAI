"""
app/repositories/marketplace_repository.py

Repository layer for marketplace packages, tenant installations, and compatibility audit logs.
"""
import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketplace_package import MarketplacePackage
from app.models.agent_installation import AgentInstallation
from app.models.agent_compatibility_log import AgentCompatibilityLog
from app.models.enums import AgentLifecycleStatus, AgentInstallationStatus


class MarketplaceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_package_by_id(self, package_id: uuid.UUID) -> Optional[MarketplacePackage]:
        stmt = select(MarketplacePackage).where(MarketplacePackage.id == package_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_package_by_name(self, package_name: str) -> Optional[MarketplacePackage]:
        stmt = select(MarketplacePackage).where(MarketplacePackage.package_name == package_name)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_package(self, package: MarketplacePackage) -> MarketplacePackage:
        self.db.add(package)
        await self.db.flush()
        return package

    async def list_published_packages(self) -> List[MarketplacePackage]:
        stmt = select(MarketplacePackage).where(
            MarketplacePackage.lifecycle_status == AgentLifecycleStatus.PUBLISHED
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_installation(self, org_id: uuid.UUID, package_id: uuid.UUID) -> Optional[AgentInstallation]:
        stmt = select(AgentInstallation).where(
            AgentInstallation.organization_id == org_id,
            AgentInstallation.package_id == package_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_installation(self, installation: AgentInstallation) -> AgentInstallation:
        self.db.add(installation)
        await self.db.flush()
        return installation

    async def list_installations(self, org_id: uuid.UUID) -> List[AgentInstallation]:
        stmt = select(AgentInstallation).where(AgentInstallation.organization_id == org_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def log_compatibility_check(self, log_entry: AgentCompatibilityLog) -> AgentCompatibilityLog:
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry
