import uuid
from app.services.communication_service import CommunicationService
from app.schemas.communication import CommunicationSendRequest
from app.models.enums import CommunicationChannel, RecipientType


class CommunicationTool:
    """Tool handler managing CRM outbound message sending operations."""

    async def execute(self, db, ctx, arguments: dict) -> dict:
        action = arguments.get("action", "send_communication")
        service = CommunicationService(db)

        if action in ("send_communication", "send_whatsapp", "send_email"):
            channel_val = arguments.get("channel", "EMAIL")
            try:
                channel = CommunicationChannel[channel_val]
            except KeyError:
                channel = CommunicationChannel.EMAIL

            lead_id_str = arguments.get("lead_id")
            lead_id = uuid.UUID(lead_id_str) if lead_id_str else None

            payload = CommunicationSendRequest(
                channel=channel,
                recipient_type=RecipientType.LEAD,
                lead_id=lead_id,
                subject=arguments.get("subject", "Follow up from Sales Executive"),
                body=arguments.get("body", "Hi, just checking in.")
            )

            comm = await service.queue_communication(ctx, payload)
            return {
                "id": str(comm.id),
                "channel": comm.channel.value if hasattr(comm.channel, "value") else comm.channel,
                "status": comm.status.value if hasattr(comm.status, "value") else comm.status,
                "recipient": comm.recipient,
                "subject": comm.subject
            }
        else:
            raise ValueError(f"Unsupported communication action: {action}")
