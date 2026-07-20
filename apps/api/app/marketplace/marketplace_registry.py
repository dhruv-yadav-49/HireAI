"""
app/marketplace/marketplace_registry.py

Marketplace Source of Truth Registry.

CTO Refinement #6:
  Acts as single source of truth for packages, versions (latest_version, stable_version, beta_version),
  and active tenant agent installations. Everything reads from it.
"""
import uuid
from typing import Any, Dict, List, Optional
from app.marketplace.package_builder import AgentPackage


class MarketplaceRegistryEntry:
    """Registry entry for a published agent package."""

    def __init__(
        self,
        package_name: str,
        display_name: str,
        latest_version: str,
        stable_version: Optional[str] = None,
        beta_version: Optional[str] = None,
        package_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.package_name = package_name
        self.display_name = display_name
        self.latest_version = latest_version
        self.stable_version = stable_version or latest_version
        self.beta_version = beta_version
        self.package_data = package_data or {}


class MarketplaceRegistry:
    """Source of truth repository for all published marketplace agents and pinned versions (CTO #6)."""

    def __init__(self) -> None:
        self._entries: Dict[str, MarketplaceRegistryEntry] = {}
        self._packages: Dict[str, AgentPackage] = {}

    def register_package(self, package: AgentPackage, stable: bool = True) -> MarketplaceRegistryEntry:
        manifest = package.manifest
        entry = MarketplaceRegistryEntry(
            package_name=manifest.name,
            display_name=manifest.display_name,
            latest_version=manifest.version,
            stable_version=manifest.version if stable else None,
            beta_version=manifest.version if not stable else None,
            package_data={"author": manifest.author, "sdk_version": manifest.sdk_version},
        )
        self._entries[manifest.name] = entry
        self._packages[manifest.name] = package
        return entry

    def get_entry(self, package_name: str) -> Optional[MarketplaceRegistryEntry]:
        return self._entries.get(package_name)

    def get_package(self, package_name: str) -> Optional[AgentPackage]:
        return self._packages.get(package_name)

    def list_entries(self) -> List[MarketplaceRegistryEntry]:
        return list(self._entries.values())
