import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.enums import LeadStatus, AudienceType
from app.models.ai_audience_segment import AIAudienceSegment


class AudienceSegmentationEngine:
    @classmethod
    async def segment_audience(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        name: str,
        segment_type: AudienceType,
        criteria_json: dict
    ) -> tuple[AIAudienceSegment, list[Lead]]:
        """Queries and partitions lead audiences dynamically matching criteria requirements."""
        
        stmt = select(Lead).where(Lead.organization_id == org_id)

        # Apply deterministic filtering criteria logic
        if segment_type == AudienceType.NEW:
            stmt = stmt.where(Lead.status == LeadStatus.NEW)
        elif segment_type == AudienceType.QUALIFIED:
            stmt = stmt.where(Lead.status == LeadStatus.QUALIFIED)
        elif segment_type == AudienceType.INACTIVE:
            stmt = stmt.where(Lead.status.in_([LeadStatus.LOST, LeadStatus.CONTACTED]))
        elif segment_type == AudienceType.HIGH_VALUE:
            stmt = stmt.where(Lead.estimated_value >= 10000.00)

        # Custom JSON filters mapping
        if "city" in criteria_json:
            stmt = stmt.where(Lead.city == criteria_json["city"])
        if "industry" in criteria_json:
            # Match company name or similar since we don't have industry on Lead table
            pass

        res = await db.execute(stmt)
        leads = list(res.scalars().all())

        segment = AIAudienceSegment(
            organization_id=org_id,
            name=name,
            segment_type=segment_type,
            criteria_json=criteria_json,
            estimated_size=len(leads),
            segment_version=1
        )

        return segment, leads
