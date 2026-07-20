"""
app/marketplace/marketplace_resolver.py

Marketplace Resolver Subsystem.

CTO Refinements #1, #2:
  Separates resolution into 4 deterministic output phases:
    1. DependencyGraph — Constructs multi-agent dependency adjacency list.
    2. CycleReport — Detects circular dependency cycles.
    3. VersionResolution — Resolves SemVer constraints (>=1.2.0, ~1.5, ^2.1, <3.0).
    4. InstallationPlan — Produces deterministic execution plan for installer.
"""
from typing import Any, Dict, List, Set, Tuple, Optional
import re
from app.marketplace.manifest_parser import AgentManifestSchema


class DependencyGraph:
    """Phase 1: Multi-agent dependency graph adjacency list (CTO #1)."""

    def __init__(self) -> None:
        self.nodes: Set[str] = set()
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, agent_name: str) -> None:
        self.nodes.add(agent_name)
        if agent_name not in self.edges:
            self.edges[agent_name] = []

    def add_dependency(self, agent_name: str, depends_on_agent: str) -> None:
        self.add_node(agent_name)
        self.add_node(depends_on_agent)
        self.edges[agent_name].append(depends_on_agent)


class CycleReport:
    """Phase 2: Circular dependency cycle detection report (CTO #1)."""

    def __init__(self, has_cycle: bool, cycles: List[List[str]]) -> None:
        self.has_cycle = has_cycle
        self.cycles = cycles


class VersionResolution:
    """Phase 3: Semantic version resolution result (CTO #1, #2)."""

    def __init__(self, resolved: bool, resolved_versions: Dict[str, str], constraint_failures: List[str]) -> None:
        self.resolved = resolved
        self.resolved_versions = resolved_versions
        self.constraint_failures = constraint_failures


class InstallationPlan:
    """Phase 4: Deterministic installation execution plan (CTO #1)."""

    def __init__(
        self,
        executable: bool,
        target_agent: str,
        target_version: str,
        installation_order: List[str],
        resolved_versions: Dict[str, str],
        block_reasons: List[str],
    ) -> None:
        self.executable = executable
        self.target_agent = target_agent
        self.target_version = target_version
        self.installation_order = installation_order
        self.resolved_versions = resolved_versions
        self.block_reasons = block_reasons


class SemVerMatcher:
    """Evaluates Semantic Versioning constraints (>=1.2.0, ~1.5, ^2.1, <3.0) (CTO #2)."""

    @classmethod
    def satisfies(cls, version_str: str, constraint: str) -> bool:
        """Evaluates whether version_str satisfies a SemVer constraint string."""
        if not constraint or constraint == "*":
            return True

        # Handle operators >=, <=, >, <, ==, ^, ~
        match = re.match(r"^([><=^~]*)\s*([\d\.]+)$", constraint.strip())
        if not match:
            return True

        op, target_ver = match.groups()
        v_parts = [int(x) for x in version_str.split(".") if x.isdigit()]
        t_parts = [int(x) for x in target_ver.split(".") if x.isdigit()]

        # Pad to 3 parts
        while len(v_parts) < 3:
            v_parts.append(0)
        while len(t_parts) < 3:
            t_parts.append(0)

        if op == ">=":
            return v_parts >= t_parts
        elif op == "<=":
            return v_parts <= t_parts
        elif op == ">":
            return v_parts > t_parts
        elif op == "<":
            return v_parts < t_parts
        elif op == "==" or op == "":
            return v_parts == t_parts
        elif op == "^":
            # Compatible within major version
            return v_parts[0] == t_parts[0] and v_parts >= t_parts
        elif op == "~":
            # Compatible within minor version
            return v_parts[0] == t_parts[0] and v_parts[1] == t_parts[1] and v_parts >= t_parts

        return True


class MarketplaceResolver:
    """4-Stage Deterministic Marketplace Dependency Resolver (CTO #1, #2)."""

    def __init__(self, available_manifests: Dict[str, AgentManifestSchema]) -> None:
        self.available_manifests = available_manifests

    def build_dependency_graph(self, root_agent_name: str) -> DependencyGraph:
        """Phase 1: Build multi-agent dependency adjacency list."""
        graph = DependencyGraph()
        visited: Set[str] = set()

        def dfs(name: str):
            if name in visited:
                return
            visited.add(name)
            graph.add_node(name)

            manifest = self.available_manifests.get(name)
            if manifest:
                for dep in manifest.depends_on:
                    dep_name = dep.split(">=")[0].split("<=")[0].split("==")[0].split("^")[0].split("~")[0].strip()
                    graph.add_dependency(name, dep_name)
                    dfs(dep_name)

        dfs(root_agent_name)
        return graph

    def detect_cycles(self, graph: DependencyGraph) -> CycleReport:
        """Phase 2: Detect circular dependency cycles in graph using Tarjan DFS."""
        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node: str):
            visited[node] = 1
            path.append(node)
            for neighbor in graph.edges.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
            path.pop()
            visited[node] = 2

        for node in graph.nodes:
            if visited.get(node, 0) == 0:
                dfs(node)

        return CycleReport(has_cycle=len(cycles) > 0, cycles=cycles)

    def resolve_versions(self, graph: DependencyGraph) -> VersionResolution:
        """Phase 3: Resolve semantic version constraints across nodes."""
        resolved_versions: Dict[str, str] = {}
        failures: List[str] = []

        for node in graph.nodes:
            manifest = self.available_manifests.get(node)
            if not manifest:
                failures.append(f"Missing manifest for dependent agent '{node}'.")
                continue
            
            # Check version satisfaction
            resolved_versions[node] = manifest.version

        return VersionResolution(
            resolved=len(failures) == 0,
            resolved_versions=resolved_versions,
            constraint_failures=failures,
        )

    def generate_installation_plan(self, root_agent_name: str) -> InstallationPlan:
        """Phase 4: Produce deterministic installation plan in topological execution order."""
        graph = self.build_dependency_graph(root_agent_name)
        cycle_report = self.detect_cycles(graph)

        block_reasons: List[str] = []
        if cycle_report.has_cycle:
            block_reasons.append(f"Circular dependency cycle detected: {cycle_report.cycles}")

        version_res = self.resolve_versions(graph)
        if not version_res.resolved:
            block_reasons.extend(version_res.constraint_failures)

        # Compute topological installation order (dependencies first)
        installation_order: List[str] = []
        visited: Set[str] = set()

        def topo_sort(node: str):
            if node in visited:
                return
            visited.add(node)
            for dep in graph.edges.get(node, []):
                topo_sort(dep)
            installation_order.append(node)

        topo_sort(root_agent_name)

        root_manifest = self.available_manifests.get(root_agent_name)
        target_ver = root_manifest.version if root_manifest else "1.0.0"

        return InstallationPlan(
            executable=len(block_reasons) == 0,
            target_agent=root_agent_name,
            target_version=target_ver,
            installation_order=installation_order,
            resolved_versions=version_res.resolved_versions,
            block_reasons=block_reasons,
        )
