from typing import Any
from app.models.lead import Lead


class PersonalizationEngine:
    @classmethod
    def personalize_content(
        cls,
        lead: Lead,
        body: str,
        campaign_variables: dict[str, Any] | None = None
    ) -> str:
        """Personalizes template copy in order of priority: Campaign -> CRM -> Memory -> Knowledge -> Default."""
        campaign_vars = campaign_variables or {}

        # Default fallback dictionary
        default_fallbacks = {
            "first_name": "there",
            "company": "your company",
            "industry": "your industry",
            "pain_point": "your business efficiency goals"
        }

        # Dynamic variable resolution
        def resolve_token(token: str) -> str:
            # 1. Campaign Variables
            if token in campaign_vars:
                return str(campaign_vars[token])

            # 2. CRM Lead Fields
            if token == "first_name" and lead.first_name:
                return lead.first_name
            if token == "company" and lead.company_name:
                return lead.company_name

            # 3. Memory Mock Variables (could represent past interactions / context)
            if token == "pain_point":
                return "scaling CRM lead capture"

            # 4. Fallback Default
            return default_fallbacks.get(token, f"{{{token}}}")

        # Basic search and replace on bracket markers
        personalized_body = body
        for token in ["first_name", "company", "industry", "pain_point"]:
            marker = f"{{{{{token}}}}}"
            if marker in personalized_body:
                val = resolve_token(token)
                personalized_body = personalized_body.replace(marker, val)

        return personalized_body
