import uuid
import time
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, get_event_publisher
from app.models.enums import EvaluationStatus, EvaluationMetric, AgentType
from app.models.ai_execution_trace import AIExecutionTrace
from app.models.ai_evaluation import AIEvaluation
from app.models.ai_evaluation_metric import AIEvaluationMetric

from app.services.grounding_evaluator import GroundingEvaluator
from app.services.retrieval_evaluator import RetrievalEvaluator
from app.services.planning_evaluator import PlanningEvaluator
from app.services.reasoning_evaluator import ReasoningEvaluator
from app.services.tool_evaluator import ToolEvaluator
from app.services.policy_evaluator import PolicyEvaluator
from app.services.latency_evaluator import LatencyEvaluator
from app.services.cost_evaluator import CostEvaluator
from app.services.hallucination_evaluator import HallucinationEvaluator
from app.services.evaluation_aggregator import EvaluationAggregator


class EvaluationEngine:
    """Core orchestrator executing all independent evaluators to compile objective quality scores."""

    @classmethod
    async def evaluate_execution(
        cls,
        db: AsyncSession,
        execution_trace_id: uuid.UUID
    ) -> Optional[AIEvaluation]:
        """Runs the complete evaluation pipeline for a trace.

        ADR-017: Evaluator Independence, Versioned Scoring, explainable outputs.
        """
        # Fetch trace & spans from repository / DB
        trace = await db.get(AIExecutionTrace, execution_trace_id)
        if not trace:
            return None

        # Fetch spans manually to bypass context restrictions
        from app.models.ai_prompt_trace import AIPromptTrace
        from app.models.ai_retrieval_trace import AIRetrievalTrace
        from app.models.ai_reasoning_trace import AIReasoningTrace
        from app.models.ai_planning_trace import AIPlanningTrace
        from app.models.ai_policy_trace import AIPolicyTrace
        from app.models.ai_tool_trace import AIToolTrace

        async def fetch(model, id_col):
            res = await db.execute(
                select(model).where(id_col == execution_trace_id).order_by(model.step_index)
            )
            return res.scalars().all()

        spans = {
            "prompts": await fetch(AIPromptTrace, AIPromptTrace.execution_trace_id),
            "retrievals": await fetch(AIRetrievalTrace, AIRetrievalTrace.execution_trace_id),
            "reasonings": await fetch(AIReasoningTrace, AIReasoningTrace.execution_trace_id),
            "plannings": await fetch(AIPlanningTrace, AIPlanningTrace.execution_trace_id),
            "policies": await fetch(AIPolicyTrace, AIPolicyTrace.execution_trace_id),
            "tools": await fetch(AIToolTrace, AIToolTrace.execution_trace_id)
        }

        # Initialize evaluation record
        evaluation = AIEvaluation(
            organization_id=trace.organization_id,
            execution_trace_id=execution_trace_id,
            agent_type=trace.agent_type,
            status=EvaluationStatus.RUNNING,
            evaluation_version=1,
            evaluation_model="RULE_ENGINE_V1",
            evaluation_trace={},
            evaluation_timeline={"started_at": datetime.now(timezone.utc).isoformat()}
        )
        db.add(evaluation)
        await db.flush()

        await cls._publish_event(trace.organization_id, "evaluation.started", {
            "evaluation_id": str(evaluation.id),
            "execution_trace_id": str(execution_trace_id)
        })

        try:
            # Run independent evaluators (CTO refinement #11: evaluate timeline execution)
            timeline = {}
            metric_results = {}

            async def run_eval(metric_key, evaluator_class):
                start = time.time()
                res = await evaluator_class.evaluate(db, trace, spans)
                duration = int((time.time() - start) * 1000)
                timeline[metric_key.value] = {
                    "duration_ms": duration,
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }
                metric_results[metric_key] = res
                return res

            # Sequence execution
            await run_eval(EvaluationMetric.GROUNDING, GroundingEvaluator)
            await run_eval(EvaluationMetric.RETRIEVAL, RetrievalEvaluator)
            await run_eval(EvaluationMetric.PLANNING, PlanningEvaluator)
            await run_eval(EvaluationMetric.REASONING, ReasoningEvaluator)
            await run_eval(EvaluationMetric.TOOLS, ToolEvaluator)
            await run_eval(EvaluationMetric.POLICY, PolicyEvaluator)
            await run_eval(EvaluationMetric.LATENCY, LatencyEvaluator)
            await run_eval(EvaluationMetric.COST, CostEvaluator)
            await run_eval(EvaluationMetric.HALLUCINATION, HallucinationEvaluator)

            # Aggregate scores
            scores_map = {k: v["score"] for k, v in metric_results.items()}
            agg = await EvaluationAggregator.aggregate(db, trace.organization_id, scores_map)

            # Save metrics
            weights = EvaluationAggregator.DEFAULT_WEIGHTS
            for m_type, res in metric_results.items():
                m_row = AIEvaluationMetric(
                    evaluation_id=evaluation.id,
                    metric_type=m_type,
                    score=res["score"],
                    weight=weights.get(m_type, 0.0),
                    details_json={
                        "inputs": res.get("inputs"),
                        "outputs": res.get("outputs"),
                        "score": res.get("score"),
                        "explanation": res.get("explanation"),
                        "warnings": res.get("warnings")
                    }
                )
                db.add(m_row)

            # Finalize overall evaluation
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.overall_score = agg["overall_score"]
            evaluation.quality_grade = agg["quality_grade"]
            
            # Setup explanation trace and timeline
            evaluation.evaluation_trace = {
                k.value: v["explanation"] for k, v in metric_results.items()
            }
            timeline["completed_at"] = datetime.now(timezone.utc).isoformat()
            evaluation.evaluation_timeline = timeline
            
            # Aggregate warnings in summary
            all_warnings = []
            for res in metric_results.values():
                all_warnings.extend(res.get("warnings", []))
            all_warnings.extend(agg.get("rules_warnings", []))

            evaluation.summary = (
                f"Grade: {agg['quality_grade'].value}. Reliability: {agg['reliability']}. "
                f"Detected {len(all_warnings)} warnings. Rules overridden: {agg['forced_fail']}."
            )

            await db.flush()

            await cls._publish_event(trace.organization_id, "evaluation.completed", {
                "evaluation_id": str(evaluation.id),
                "overall_score": agg["overall_score"],
                "quality_grade": agg["quality_grade"].value
            })

            return evaluation

        except Exception as err:
            evaluation.status = EvaluationStatus.FAILED
            evaluation.summary = f"Evaluation failed during processing pipeline: {str(err)}"
            await db.flush()

            await cls._publish_event(trace.organization_id, "evaluation.failed", {
                "evaluation_id": str(evaluation.id),
                "error": str(err)
            })
            raise err

    @staticmethod
    async def _publish_event(org_id: uuid.UUID, event_name: str, payload: dict) -> None:
        """Publishes local domain events inside transaction."""
        event = DomainEvent(
            event_name=event_name,
            tenant_id=org_id,
            request_id=uuid.uuid4(),
            actor_id=None,
            payload=payload
        )
        try:
            pub = get_event_publisher()
            await pub.publish(event)
        except Exception:
            pass
