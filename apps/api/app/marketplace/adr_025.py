"""
app/marketplace/adr_025.py

ADR-025: Agent Marketplace Experience & Dependency Resolution Contracts.

CTO Refinement #10:
  1. Resolver Before Installation: Every installation request is resolved into a deterministic execution plan before changes are applied.
  2. Semantic Version Resolution: Dependency constraints are interpreted using semantic versioning rules.
  3. Explainable Installation: Compatibility failures should explain why an installation cannot proceed.
  4. Tenant-Aware Discovery: Catalog results are filtered according to tenant compatibility and permissions.
  5. Immutable Release History: Published package versions are immutable.
  6. Community Trust: Publisher identity and community feedback are first-class marketplace concepts.
"""

ADR_025_TITLE = "ADR-025: Agent Marketplace Experience Architecture Principles"

ADR_025_PRINCIPLES = {
    "Resolver_Before_Installation": "Every installation request is resolved into a deterministic execution plan before changes are applied.",
    "Semantic_Version_Resolution": "Dependency constraints are interpreted using semantic versioning rules.",
    "Explainable_Installation": "Compatibility failures should explain why an installation cannot proceed.",
    "Tenant_Aware_Discovery": "Catalog results are filtered according to tenant compatibility and permissions.",
    "Immutable_Release_History": "Published package versions are immutable.",
    "Community_Trust": "Publisher identity and community feedback are first-class marketplace concepts.",
}
