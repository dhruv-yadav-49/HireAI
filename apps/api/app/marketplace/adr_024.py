"""
app/marketplace/adr_024.py

ADR-024: Agent Marketplace Architecture Principles & System Contracts.

CTO Refinement #13:
  1. Package as Artifact: Agents are immutable deployable packages (.hireagent).
  2. Registry as Source of Truth: Marketplace Registry owns package metadata and lifecycle.
  3. Validation Before Installation: Packages must pass explicit 6-stage validation.
  4. Versioned Manifests: Manifest schemas evolve independently from runtime versions.
  5. Dependency Awareness: Agent compatibility includes runtime, SDK, tools, models, and policy requirements.
  6. Platform Reuse: Validation composes Playground, Security, Governance, and Runtime capabilities.
"""

ADR_024_TITLE = "ADR-024: Agent Marketplace Architecture Principles"

ADR_024_PRINCIPLES = {
    "Package_as_Artifact": "Agents are immutable deployable packages (.hireagent).",
    "Registry_as_Source_of_Truth": "Marketplace Registry owns package metadata and lifecycle.",
    "Validation_Before_Installation": "Packages must pass explicit 6-stage validation.",
    "Versioned_Manifests": "Manifest schemas evolve independently from runtime versions.",
    "Dependency_Awareness": "Agent compatibility includes runtime, SDK, tools, models, and policy requirements.",
    "Platform_Reuse": "Validation composes Playground, Security, Governance, and Runtime capabilities.",
}
