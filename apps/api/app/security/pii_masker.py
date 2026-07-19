"""
app/security/pii_masker.py

Type-specific PII masking.

Masking rules:
    EMAIL:       john.doe@example.com  →  j***@example.com
    PHONE:       +919876543210         →  +91-XXXX-XX-3210
    PAN:         ABCDE1234F            →  XXXXX1234F
    AADHAAR:     1234 5678 9012        →  XXXX-XXXX-9012
    CREDIT_CARD: 4111111111111111      →  XXXX-XXXX-XXXX-1111

ADR-021: Privacy by Default — masking is applied before any persistence,
logging, or event publication.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from app.models.enums import PIIType
from app.security.pii_detector import PIIMatch


class PIIMasker:
    """Applies type-specific masking to detected PII."""

    @staticmethod
    def mask_value(match: PIIMatch) -> str:
        """Return a masked version of the matched PII value."""
        value = match.value
        pii_type = match.pii_type

        if pii_type == PIIType.EMAIL:
            return PIIMasker._mask_email(value)
        elif pii_type == PIIType.PHONE:
            return PIIMasker._mask_phone(value)
        elif pii_type == PIIType.PAN:
            return PIIMasker._mask_pan(value)
        elif pii_type == PIIType.AADHAAR:
            return PIIMasker._mask_aadhaar(value)
        elif pii_type == PIIType.CREDIT_CARD:
            return PIIMasker._mask_credit_card(value)
        return "***"

    # ── Type-specific masking ──────────────────────────────────────────────────

    @staticmethod
    def _mask_email(email: str) -> str:
        """john.doe@example.com → j***@example.com"""
        at = email.find("@")
        if at <= 0:
            return "***@***.***"
        local = email[:at]
        domain = email[at:]
        masked_local = local[0] + "***" if len(local) > 1 else "***"
        return masked_local + domain

    @staticmethod
    def _mask_phone(phone: str) -> str:
        """Keep last 4 digits visible: +91-XXXX-XX-3210"""
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 4:
            visible = digits[-4:]
            return f"+XX-XXXX-XX-{visible}"
        return "XXXX-XXXX"

    @staticmethod
    def _mask_pan(pan: str) -> str:
        """ABCDE1234F → XXXXX1234F"""
        if len(pan) == 10:
            return f"XXXXX{pan[5:]}"
        return "XXXXXXXXXX"

    @staticmethod
    def _mask_aadhaar(aadhaar: str) -> str:
        """1234 5678 9012 → XXXX-XXXX-9012"""
        digits = re.sub(r"\D", "", aadhaar)
        if len(digits) == 12:
            return f"XXXX-XXXX-{digits[-4:]}"
        return "XXXX-XXXX-XXXX"

    @staticmethod
    def _mask_credit_card(card: str) -> str:
        """4111111111111111 → XXXX-XXXX-XXXX-1111"""
        digits = re.sub(r"\D", "", card)
        if len(digits) >= 4:
            return f"XXXX-XXXX-XXXX-{digits[-4:]}"
        return "XXXX-XXXX-XXXX-XXXX"

    # ── Text masking ───────────────────────────────────────────────────────────

    @staticmethod
    def mask(text: str, matches: List[PIIMatch]) -> str:
        """Replace all PII matches in text with masked equivalents.

        Processes matches in reverse order to preserve original offsets.
        """
        if not matches:
            return text

        # Sort by start index descending to preserve offsets
        sorted_matches = sorted(matches, key=lambda m: m.start, reverse=True)

        result = text
        for match in sorted_matches:
            masked = PIIMasker.mask_value(match)
            result = result[: match.start] + masked + result[match.end :]

        return result

    @staticmethod
    def mask_dict(payload: Dict[str, Any], matches: List[PIIMatch]) -> Dict[str, Any]:
        """Return a deep copy of payload with PII values replaced.

        Uses detector location path (stored in match.detector) to route
        masking to the correct field.
        """
        import copy
        result = copy.deepcopy(payload)

        for match in matches:
            # Detector encodes location as "regex@field.subfield[0]"
            location = match.detector
            if "@" in location:
                path = location.split("@", 1)[1]
                # Remove array indices for dict traversal
                path = re.sub(r"\[\d+\]", "", path)
                parts = path.split(".")
                # Navigate to the parent and replace
                obj = result
                for part in parts[:-1]:
                    if isinstance(obj, dict):
                        obj = obj.get(part, {})
                last = parts[-1]
                if isinstance(obj, dict) and last in obj:
                    if isinstance(obj[last], str):
                        from app.security.pii_detector import PIIDetector
                        detector = PIIDetector()
                        sub_matches = detector.scan(obj[last])
                        if sub_matches:
                            obj[last] = PIIMasker.mask(obj[last], sub_matches)

        return result
