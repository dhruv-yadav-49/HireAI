import uuid
from app.services.lead_service import LeadService
from app.schemas.lead import LeadCreateRequest


class LeadTool:
    """Tool handler managing CRM Lead operations (Creation, Search, Updates)."""

    async def execute(self, db, ctx, arguments: dict) -> dict:
        action = arguments.get("action", "create_lead")
        if action == "create_lead":
            service = LeadService(db)
            lead_data = arguments.get("lead_data", {})
            # Populate required placeholders
            if "job_title" not in lead_data:
                lead_data["job_title"] = "Manager"
            if "company_name" not in lead_data:
                lead_data["company_name"] = "Default Corp"

            payload = LeadCreateRequest(**lead_data)
            lead = await service.create_lead(ctx, payload)
            return {
                "id": str(lead.id),
                "lead_number": lead.lead_number,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "status": lead.status,
                "organization_id": str(lead.organization_id)
            }
        else:
            raise ValueError(f"Unsupported lead action: {action}")
