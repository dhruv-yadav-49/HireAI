"""
app/playground/interfaces.py

Reserved Interfaces for Future Playground Expansion.

CTO Refinement #14: Future compatibility hooks:
  - PromptABDeploymentSpec
  - HumanEvaluationSpec
  - TeamSharedExperimentSpec
  - BenchmarkDatasetSpec
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class PromptABDeploymentSpec:
    """Spec for deploying prompt A/B test variations to production."""
    prompt_a_id: str
    prompt_b_id: str
    traffic_split_percentage: float = 50.0


@dataclass
class HumanEvaluationSpec:
    """Spec for human evaluator feedback on playground prompt outputs."""
    experiment_id: str
    evaluator_user_id: str
    rating: int  # 1 to 5
    notes: Optional[str] = None


@dataclass
class BenchmarkDatasetSpec:
    """Spec for running playground prompt suites against benchmark datasets."""
    dataset_name: str
    sample_count: int
    ground_truth_key: str


class BaseBenchmarkEvaluator(ABC):
    """Abstract interface for benchmark dataset evaluators."""

    @abstractmethod
    def evaluate_dataset(self, dataset: BenchmarkDatasetSpec, prompt_template: str) -> Dict[str, Any]:
        ...
