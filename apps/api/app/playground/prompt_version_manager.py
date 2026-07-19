"""
app/playground/prompt_version_manager.py

Prompt Version Manager for developer playground.

Connects with Sprint 5A AIPrompt versioning without storage duplication.
"""
import uuid
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ai_prompt import AIPrompt


class PromptVersionManager:
    """Connector reading and resolving AIPrompt template versions."""

    @staticmethod
    async def get_prompt_version(
        db: AsyncSession, org_id: uuid.UUID, prompt_name: str, version: Optional[int] = None
    ) -> Optional[AIPrompt]:
        stmt = select(AIPrompt).where(
            AIPrompt.organization_id == org_id,
            AIPrompt.name == prompt_name,
        )
        if version:
            stmt = stmt.where(AIPrompt.version == version)
        else:
            stmt = stmt.order_by(AIPrompt.version.desc()).limit(1)

        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_versions(
        db: AsyncSession, org_id: uuid.UUID, prompt_name: str
    ) -> List[AIPrompt]:
        stmt = (
            select(AIPrompt)
            .where(
                AIPrompt.organization_id == org_id,
                AIPrompt.name == prompt_name,
            )
            .order_by(AIPrompt.version.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
