"""
app/security/pii_detector.py

Plugin-chain PII detector.

CTO refinement #7: Detectors are structured as plugins implementing BaseDetector.
Only RegexDetector is implemented now. NERDetector and LLMDetector follow the
same interface when needed.

ADR-021: Privacy by Default — scan is applied before persistence or publication.
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from app.models.enums import PIIType


@dataclass
class PIIMatch:
    """A single PII detection result."""
    pii_type: PIIType
    value: str           # The matched text
    start: int           # Start index in original string
    end: int             # End index in original string
    confidence: float    # 0.0 – 1.0
    detector: str        # Which detector found it


# ── Base detector interface (CTO refinement #7) ───────────────────────────────

class BaseDetector(ABC):
    """Abstract detector plugin. Each detector scans text for a set of PII types."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def scan(self, text: str) -> List[PIIMatch]:
        """Scan text and return all PII matches."""
        ...


# ── Regex Detector ─────────────────────────────────────────────────────────────

# Luhn algorithm for credit card validation
def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10 == 0


_PATTERNS = {
    PIIType.EMAIL: re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    PIIType.PHONE: re.compile(
        r"(?:\+91[\-\s]?)?[6-9]\d{9}"           # Indian mobile
        r"|(?:\+1[\-\s]?)?\(?\d{3}\)?[\-\s]\d{3}[\-\s]\d{4}"  # US
    ),
    PIIType.PAN: re.compile(
        r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"            # Indian PAN card
    ),
    PIIType.AADHAAR: re.compile(
        r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"   # 12-digit Aadhaar
    ),
    PIIType.CREDIT_CARD: re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"        # Visa
        r"5[1-5][0-9]{14}|"                      # MasterCard
        r"3[47][0-9]{13}|"                       # Amex
        r"6(?:011|5[0-9]{2})[0-9]{12})\b"        # Discover
    ),
}

_CONFIDENCE = {
    PIIType.EMAIL: 0.95,
    PIIType.PHONE: 0.80,
    PIIType.PAN: 0.90,
    PIIType.AADHAAR: 0.75,      # Lower: 12-digit sequences are common
    PIIType.CREDIT_CARD: 0.85,
}


class RegexDetector(BaseDetector):
    """Regex-based PII detector — fast, zero dependencies."""

    @property
    def name(self) -> str:
        return "regex"

    def scan(self, text: str) -> List[PIIMatch]:
        if not text:
            return []

        matches: List[PIIMatch] = []

        for pii_type, pattern in _PATTERNS.items():
            for m in pattern.finditer(text):
                value = m.group()
                confidence = _CONFIDENCE.get(pii_type, 0.80)

                # Boost credit card confidence if Luhn passes
                if pii_type == PIIType.CREDIT_CARD:
                    digits_only = re.sub(r"\D", "", value)
                    if not _luhn_check(digits_only):
                        continue
                    confidence = 1.0

                # Aadhaar: skip if it's clearly a phone or PIN
                if pii_type == PIIType.AADHAAR:
                    digits_only = re.sub(r"\D", "", value)
                    if len(digits_only) != 12:
                        continue

                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=value,
                    start=m.start(),
                    end=m.end(),
                    confidence=confidence,
                    detector=self.name,
                ))

        return matches


# ── PII Detector (plugin chain) ───────────────────────────────────────────────

class PIIDetector:
    """Plugin-chain PII scanner.

    Detectors run in order. Results from all detectors are merged.
    Duplicate matches (same span, different detectors) keep the highest confidence.

    CTO refinement #7: Add NERDetector / LLMDetector by appending to detectors list.
    """

    def __init__(self, detectors: Optional[List[BaseDetector]] = None) -> None:
        self._detectors = detectors or [RegexDetector()]

    def scan(self, text: str) -> List[PIIMatch]:
        """Scan text through all detector plugins."""
        if not text:
            return []

        all_matches: List[PIIMatch] = []
        for detector in self._detectors:
            all_matches.extend(detector.scan(text))

        # Deduplicate: keep highest-confidence match per (start, pii_type)
        best: dict[tuple, PIIMatch] = {}
        for match in all_matches:
            key = (match.start, match.pii_type)
            existing = best.get(key)
            if existing is None or match.confidence > existing.confidence:
                best[key] = match

        return sorted(best.values(), key=lambda m: m.start)

    def scan_dict(self, payload: dict, path_prefix: str = "") -> List[PIIMatch]:
        """Recursively scan all string values in a dict."""
        results: List[PIIMatch] = []
        for k, v in payload.items():
            current_path = f"{path_prefix}.{k}" if path_prefix else k
            if isinstance(v, str):
                for match in self.scan(v):
                    # Annotate with the dict path for incident location
                    results.append(PIIMatch(
                        pii_type=match.pii_type,
                        value=match.value,
                        start=match.start,
                        end=match.end,
                        confidence=match.confidence,
                        detector=f"{match.detector}@{current_path}",
                    ))
            elif isinstance(v, dict):
                results.extend(self.scan_dict(v, current_path))
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, str):
                        for match in self.scan(item):
                            results.append(PIIMatch(
                                pii_type=match.pii_type,
                                value=match.value,
                                start=match.start,
                                end=match.end,
                                confidence=match.confidence,
                                detector=f"{match.detector}@{current_path}[{i}]",
                            ))
        return results

    def add_detector(self, detector: BaseDetector) -> None:
        """Register an additional detector in the plugin chain."""
        self._detectors.append(detector)


# ── Application singleton ──────────────────────────────────────────────────────
_default_detector = PIIDetector()


def get_pii_detector() -> PIIDetector:
    return _default_detector
