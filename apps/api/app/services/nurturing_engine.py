from typing import Any


class NurturingEngine:
    @classmethod
    def compile_nurturing_graph(
        cls,
        steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Translates step configs list into a formalized workflow DAG graph matching Sprint 5D requirements."""
        nodes = []
        edges = []

        prev_node_id = None

        for idx, step in enumerate(steps):
            # 1. Action Node
            action_id = f"step_{idx}_action"
            nodes.append({
                "id": action_id,
                "type": "COMMUNICATION_OUTBOUND",
                "channel": step["channel"],
                "template": step.get("template")
            })

            # Edge to connect previous node
            if prev_node_id:
                edges.append({
                    "source": prev_node_id,
                    "target": action_id
                })

            # 2. Wait Node (if not the last step)
            if idx < len(steps) - 1:
                wait_id = f"step_{idx}_wait"
                # Calculate next duration delta
                next_day = steps[idx + 1]["day"]
                curr_day = step["day"]
                wait_days = max(next_day - curr_day, 1)

                nodes.append({
                    "id": wait_id,
                    "type": "WAIT_DURATION",
                    "duration_days": wait_days
                })

                # Connect action step to its following wait step
                edges.append({
                    "source": action_id,
                    "target": wait_id
                })

                prev_node_id = wait_id
            else:
                prev_node_id = action_id

        return {
            "nodes": nodes,
            "edges": edges
        }
