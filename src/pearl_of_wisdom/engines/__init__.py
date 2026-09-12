"""Probabilistic engines used by Pearl of Wisdom."""

from .discrete_bayes import DiscreteBayesEngine, DiscreteBayesValidationError
from .monte_carlo import MAX_SAMPLES, MonteCarloEngine, MonteCarloValidationError
from .protocol import AnalysisEngine, AnalysisResult

ENGINE_FACTORIES: dict[str, type[AnalysisEngine]] = {
    "discrete-bayes": DiscreteBayesEngine,
    "monte-carlo": MonteCarloEngine,
}

__all__ = [
    "AnalysisEngine",
    "AnalysisResult",
    "DiscreteBayesEngine",
    "DiscreteBayesValidationError",
    "ENGINE_FACTORIES",
    "MAX_SAMPLES",
    "MonteCarloEngine",
    "MonteCarloValidationError",
]
