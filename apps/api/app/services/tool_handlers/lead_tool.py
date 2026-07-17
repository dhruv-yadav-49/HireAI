import uuid
from app.services.lead_service import LeadService
from app.schemas.lead import LeadCreateRequest, LeadUpdateRequest
from app.models.enums import LeadStatus


class LeadTool:
    """Tool handler managing CRM Lead operations (Creation, Search, Updates)."""

    async def execute(self, db, ctx, arguments: dict) -> dict:
        action = arguments.get("action", "create_lead")
        service = LeadService(db)

        if action == "create_lead":
            lead_data = arguments.get("lead_data", {})
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
                "status": lead.status.value if hasattr(lead.status, "value") else lead.status,
                "organization_id": str(lead.organization_id)
            }

        elif action in ("update_lead", "change_status"):
            lead_id_str = arguments.get("lead_id")
            if not lead_id_str:
                raise ValueError("lead_id is required for update_lead action.")
            lead_id = uuid.UUID(str(lead_id_str))

            lead_data = arguments.get("lead_data", {})
            
            # Map status if present
            status_val = lead_data.get("status")
            if status_val and isinstance(status_val, str):
                try:
                    lead_data["status"] = LeadStatus[status_val]
                except KeyError:
                    lead_data["status"] = LeadStatus.CONTACTED

            payload = LeadUpdateRequest(**lead_data)
            lead = await service.update_lead(ctx, lead_id, payload)
            return {
                "id": str(lead.id),
                "lead_number": lead.lead_number,
                "status": lead.status.value if hasattr(lead.status, "value") else lead.status,
                "version": lead.version
            }

        else:
            raise ValueError(f"Unsupported lead action: {action}")
