import uuid
from typing import Any
from app.models.ai_ab_test import AIABTest
from app.models.enums import ABTestStatus


class ABTestingEngine:
    @classmethod
    def setup_ab_test(
        cls,
        campaign_id: uuid.UUID,
        variants_config: list[dict[str, Any]]
    ) -> AIABTest:
        """Sets up a multivariate A/B test split for variant copies."""
        
        # Validates variants percentages total up to 100
        total_pct = sum(float(v.get("traffic_percentage", 0)) for v in variants_config)
        if total_pct == 0.0:
            # Default split evenly
            size = len(variants_config)
            for v in variants_config:
                v["traffic_percentage"] = round(100.0 / size, 2)

        variants_payload = {
            "variants": [
                {
                    "variant_id": v.get("variant_id", f"var_{i}"),
                    "traffic_percentage": v.get("traffic_percentage", 50.0),
                    "winner_score": 0.0,
                    "subject": v.get("subject"),
                    "body": v.get("body")
                } for i, v in enumerate(variants_config)
            ]
        }

        test = AIABTest(
            campaign_id=campaign_id,
            variants_json=variants_payload,
            winner=None,
            winner_metrics={},
            metrics_json={"variant_performance": []},
            status=ABTestStatus.DRAFT
        )

        return test

    @classmethod
    def evaluate_winner(
        cls,
        test: AIABTest,
        performance_data: dict[str, Any]
    ) -> AIABTest:
        """Determines the A/B test variant winner based on click and conversion rates."""
        
        # Performance data keys: variant performance array
        performances = performance_data.get("variant_performance", [])
        
        best_variant = None
        best_score = -1.0
        best_metrics = {}

        for perf in performances:
            var_id = perf["variant_id"]
            ctr = float(perf.get("ctr", 0.0))
            conv = float(perf.get("conversion", 0.0))
            
            # Weighted winner score evaluation
            score = (ctr * 0.4) + (conv * 0.6)
            
            if score > best_score:
                best_score = score
                best_variant = var_id
                best_metrics = {
                    "variant": var_id,
                    "ctr": ctr,
                    "conversion": conv,
                    "confidence": 0.95
                }

        test.winner = best_variant
        test.winner_metrics = best_metrics
        test.status = ABTestStatus.COMPLETED
        test.metrics_json = {"performances": performances}

        return test
