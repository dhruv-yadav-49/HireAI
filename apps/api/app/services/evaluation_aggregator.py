import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_quality_profile import AIQualityProfile
from app.models.ai_quality_rule import AIQualityRule
from app.models.enums import EvaluationMetric, QualityGrade, QualityRuleAction


class EvaluationAggregator:
    """Aggregates individual evaluator scores into a final grade, confidence, and reliability levels."""

    DEFAULT_WEIGHTS = {
        EvaluationMetric.GROUNDING: 0.25,
        EvaluationMetric.RETRIEVAL: 0.15,
        EvaluationMetric.PLANNING: 0.15,
        EvaluationMetric.REASONING: 0.15,
        EvaluationMetric.TOOLS: 0.15,
        EvaluationMetric.POLICY: 0.05,
        EvaluationMetric.LATENCY: 0.05,
        EvaluationMetric.COST: 0.05,
        EvaluationMetric.HALLUCINATION: 0.05
    }

    @classmethod
    async def aggregate(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        metric_scores: dict[EvaluationMetric, float]
    ) -> dict:
        """Weighted aggregation mapping to QualityGrade (A/B/C/D/F).

        CTO refinement #8: Computes overall score, confidence, and reliability levels.
        CTO refinement #3: Loads weights from tenant's enabled AIQualityProfile.
        CTO refinement #9: Enforces AIQualityRules thresholds and actions (WARN, FAIL).
        """
        # 1. Load Custom Weights profile if exists
        weights = dict(cls.DEFAULT_WEIGHTS)
        profile_res = await db.execute(
            select(AIQualityProfile).where(
                AIQualityProfile.organization_id == org_id,
                AIQualityProfile.enabled == True
            ).limit(1)
        )
        profile = profile_res.scalar_one_or_none()
        if profile and profile.weights_json:
            for k, w in profile.weights_json.items():
                try:
                    m_key = EvaluationMetric(k)
                    weights[m_key] = float(w)
                except ValueError:
                    pass

        # Calculate weighted average
        total_weight = 0.0
        weighted_sum = 0.0
        for m_type, score in metric_scores.items():
            w = weights.get(m_type, 0.0)
            weighted_sum += score * w
            total_weight += w

        overall_score = round(weighted_sum / total_weight, 2) if total_weight > 0.0 else 0.0

        # Calculate Heuristic Confidence & Reliability
        confidence = 0.95
        if metric_scores.get(EvaluationMetric.RETRIEVAL, 100) < 60:
            confidence = 0.75
        
        reliability = "HIGH"
        if overall_score < 70:
            reliability = "LOW"
        elif overall_score < 85:
            reliability = "MEDIUM"

        # 2. Check Custom Organizational Quality Rules (CTO refinement #9)
        rules_res = await db.execute(
            select(AIQualityRule).where(
                AIQualityRule.organization_id == org_id,
                AIQualityRule.enabled == True
            )
        )
        rules = rules_res.scalars().all()
        forced_fail = False
        warnings_triggered = []

        for rule in rules:
            current_score = metric_scores.get(rule.metric_type)
            if current_score is not None and current_score < (rule.threshold * 100.0):
                if rule.action == QualityRuleAction.FAIL:
                    forced_fail = True
                warnings_triggered.append(
                    f"Quality rule '{rule.rule_name}' violated (metric: {rule.metric_type.value}, score: {current_score}, threshold: {rule.threshold * 100.0})"
                )

        # 3. Map score to Grade
        # Bounds: 95-100 A, 85-94 B, 70-84 C, 50-69 D, <50 F
        if forced_fail:
            grade = QualityGrade.F
        elif overall_score >= 95.0:
            grade = QualityGrade.A
        elif overall_score >= 85.0:
            grade = QualityGrade.B
        elif overall_score >= 70.0:
            grade = QualityGrade.C
        elif overall_score >= 50.0:
            grade = QualityGrade.D
        else:
            grade = QualityGrade.F

        return {
            "overall_score": overall_score,
            "quality_grade": grade,
            "confidence": confidence,
            "reliability": reliability,
            "forced_fail": forced_fail,
            "rules_warnings": warnings_triggered
        }
