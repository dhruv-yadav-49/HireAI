"""
app/marketplace/interfaces.py

Reserved Future Compatibility Interfaces & Extension Hooks.

CTO Refinement #14:
  Reserves extension interfaces for:
  - Private organization marketplaces
  - Signed publisher identities
  - Paid packages & package licensing
  - Automatic updates & canary deployments
  - Multi-version concurrent agent execution & hot reloads
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IPrivateOrganizationMarketplace(ABC):
    """Interface for enterprise private organization catalogs."""
    @abstractmethod
    def list_private_packages(self, org_id: str) -> List[Dict[str, Any]]:
        pass


class ISignedPublisherIdentityValidator(ABC):
    """Interface for verifying cryptographic X.509 publisher certificates."""
    @abstractmethod
    def verify_publisher_signature(self, package_bytes: bytes, signature: str) -> bool:
        pass


class IPackageLicenseEnforcer(ABC):
    """Interface for verifying commercial package entitlements and seat counts."""
    @abstractmethod
    def verify_license(self, org_id: str, package_name: str) -> bool:
        pass


class ICanaryDeploymentStrategy(ABC):
    """Interface for rolling out agent version updates using canary traffic splits."""
    @abstractmethod
    def compute_canary_split(self, old_version: str, new_version: str) -> Dict[str, float]:
        pass
