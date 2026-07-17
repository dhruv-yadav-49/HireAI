import uuid
from typing import Optional
from app.models.ai_campaign import AICampaign
from app.models.ai_marketing_content import AIMarketingContent
from app.models.enums import ContentType


class ContentGenerationEngine:
    @classmethod
    def generate_content(
        cls,
        org_id: uuid.UUID,
        campaign: AICampaign,
        content_type: ContentType,
        subject: Optional[str] = None,
        body_override: Optional[str] = None,
        parent_content_id: Optional[uuid.UUID] = None,
        generation_prompt: Optional[str] = None
    ) -> AIMarketingContent:
        """Generates campaign copy and subject lines based on the campaign's goals."""
        
        default_subjects = {
            ContentType.EMAIL: "Special Invitation for you",
            ContentType.WHATSAPP: None,
            ContentType.SMS: None
        }

        default_bodies = {
            ContentType.EMAIL: "Hi {{first_name}},\n\nWe wanted to reach out regarding {{company}}. We have some exciting updates that can help your business thrive!\n\nBest regards,\nTeam",
            ContentType.WHATSAPP: "Hi {{first_name}}, did you get our pricing guide? Let us know if you have any questions!",
            ContentType.SMS: "Hi {{first_name}}, check out our latest offers here: bit.ly/hireai-deals"
        }

        resolved_subject = subject or default_subjects.get(content_type)
        resolved_body = body_override or default_bodies.get(content_type, "Hello!")

        # Identify template variables
        variables = ["first_name", "company"]

        content = AIMarketingContent(
            organization_id=org_id,
            campaign_id=campaign.id,
            content_type=content_type,
            subject=resolved_subject,
            body=resolved_body,
            variables_json={"variables": variables},
            version=1,
            parent_content_id=parent_content_id,
            generation_prompt=generation_prompt,
            approval_id=None
        )

        return content
