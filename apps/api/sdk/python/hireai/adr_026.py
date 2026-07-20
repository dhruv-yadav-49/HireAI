"""
hireai.sdk.adr_026 — ADR-026 Architecture Principles.

CTO Refinement #11:
  1. SDK as Client: SDKs consume Marketplace and Runtime APIs without bypassing platform governance.
  2. Stable Contracts: Public SDK interfaces evolve through semantic versioning.
  3. Local-First Development: Developers scaffold, test, validate, and package agents locally.
  4. Portable Tool Contracts: Tools expose explicit metadata, schemas, and permission scopes.
  5. Deterministic Packaging: CLI and SDK packaging produce identical .hireagent artifacts.
  6. Compatibility Validation: SDK and CLI validate runtime and Marketplace compatibility before publication.
"""

ADR_026_TITLE = "ADR-026: Developer Ecosystem & SDK Architecture Principles"

ADR_026_PRINCIPLES = {
    "SDK_as_Client": "SDKs consume Marketplace and Runtime APIs without bypassing platform governance.",
    "Stable_Contracts": "Public SDK interfaces evolve through semantic versioning.",
    "Local_First_Development": "Developers scaffold, test, validate, and package agents locally.",
    "Portable_Tool_Contracts": "Tools expose explicit metadata, schemas, and permission scopes.",
    "Deterministic_Packaging": "CLI and SDK packaging produce identical .hireagent artifacts.",
    "Compatibility_Validation": "SDK and CLI validate runtime and Marketplace compatibility before publication.",
}
