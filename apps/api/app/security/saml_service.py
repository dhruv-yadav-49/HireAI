"""
app/security/saml_service.py

SAML 2.0 Service Provider stub.

Full SAML requires python3-saml or pysaml2. This stub defines the complete
interface so Sprint 7D / future sprints can plug in a real implementation
without changing the authentication pipeline.

ADR-021: Pluggable Security — SAML is one interchangeable auth method.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SAMLMetadata:
    """Parsed IdP metadata."""
    entity_id: str
    sso_url: str
    slo_url: Optional[str]
    x509_cert: str


@dataclass
class SAMLAssertion:
    """Validated SAML assertion attributes."""
    name_id: str
    email: Optional[str]
    display_name: Optional[str]
    groups: list[str]
    raw_attributes: Dict[str, Any]


class SAMLService:
    """SAML 2.0 Service Provider.

    Stub implementation — interface is complete for pipeline integration.
    Activate by installing python3-saml and implementing each method body.
    """

    @staticmethod
    def import_metadata(xml: str) -> SAMLMetadata:
        """Parse IdP XML metadata and extract SSO endpoint and certificate."""
        raise NotImplementedError(
            "Install python3-saml and implement SAMLService.import_metadata()"
        )

    @staticmethod
    def build_authn_request(
        idp_metadata: SAMLMetadata,
        relay_state: str,
        sp_acs_url: str,
        sp_entity_id: str,
    ) -> str:
        """Build a Base64-encoded SAMLRequest for redirect binding."""
        raise NotImplementedError(
            "Install python3-saml and implement SAMLService.build_authn_request()"
        )

    @staticmethod
    def validate_assertion(
        saml_response_b64: str,
        idp_metadata: SAMLMetadata,
        sp_acs_url: str,
    ) -> SAMLAssertion:
        """Validate a SAML Response and return extracted attributes.

        Validates:
            - XML signature using IdP certificate
            - Audience restriction matches SP entity ID
            - Conditions NotBefore / NotOnOrAfter
        """
        raise NotImplementedError(
            "Install python3-saml and implement SAMLService.validate_assertion()"
        )

    @staticmethod
    def extract_attributes(assertion: SAMLAssertion) -> Dict[str, Any]:
        """Map SAML assertion attributes to platform user attributes."""
        return {
            "name_id": assertion.name_id,
            "email": assertion.email,
            "display_name": assertion.display_name,
            "groups": assertion.groups,
        }

    @staticmethod
    def build_logout_request(
        name_id: str,
        idp_metadata: SAMLMetadata,
        sp_entity_id: str,
    ) -> str:
        """Build a SAMLRequest for single logout."""
        raise NotImplementedError(
            "Install python3-saml and implement SAMLService.build_logout_request()"
        )
