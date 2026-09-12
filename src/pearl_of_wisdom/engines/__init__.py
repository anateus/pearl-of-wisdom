"""Probabilistic engines used by Pearl of Wisdom."""

from .causal import CausalEngine, CausalValidationError
from .decision_analysis import DecisionAnalysisEngine, DecisionAnalysisValidationError
from .discrete_bayes import DiscreteBayesEngine, DiscreteBayesValidationError
from .monte_carlo import MAX_SAMPLES, MonteCarloEngine, MonteCarloValidationError
from .protocol import AnalysisEngine, AnalysisResult
from .system_simulation import SystemSimulationEngine, SystemSimulationValidationError

ENGINE_FACTORIES: dict[str, type[AnalysisEngine]] = {
    "causal": CausalEngine,
    "decision-analysis": DecisionAnalysisEngine,
    "discrete-bayes": DiscreteBayesEngine,
    "monte-carlo": MonteCarloEngine,
    "system-simulation": SystemSimulationEngine,
}

__all__ = [
    "AnalysisEngine",
    "AnalysisResult",
    "CausalEngine",
    "CausalValidationError",
    "DecisionAnalysisEngine",
    "DecisionAnalysisValidationError",
    "DiscreteBayesEngine",
    "DiscreteBayesValidationError",
    "ENGINE_FACTORIES",
    "MAX_SAMPLES",
    "MonteCarloEngine",
    "MonteCarloValidationError",
    "SystemSimulationEngine",
    "SystemSimulationValidationError",
]
