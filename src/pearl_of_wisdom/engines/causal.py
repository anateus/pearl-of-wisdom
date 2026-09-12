"""Exact interventions in explicitly supplied discrete causal models."""

from __future__ import annotations

from collections.abc import Mapping

from .base import require_only_fields
from .discrete_bayes import DiscreteBayesEngine, DiscreteBayesValidationError, Variable
from .protocol import AnalysisResult

REQUEST_FIELDS = {"assumptions", "evidence", "interventions", "network", "query"}
MAX_VARIABLES = 128
MAX_ASSUMPTIONS = 100
MAX_ASSUMPTION_CHARS = 4096


class CausalValidationError(DiscreteBayesValidationError):
    """Raised when a supplied causal model or intervention request is invalid."""


class CausalEngine(DiscreteBayesEngine):
    """Evaluate P(query | do(interventions), evidence) by truncated factorization.

    The supplied graph and CPTs must describe causal mechanisms, with relevant
    common causes represented. Observational data alone do not establish those
    assumptions. Evidence is conditioned on in the intervened model; this is not
    counterfactual inference about a previously observed individual.
    """

    name = "causal"
    capabilities = ("inference.causal", "inference.intervention")

    def __init__(self, *, max_states: int = 4096) -> None:
        try:
            super().__init__(max_states=max_states)
        except DiscreteBayesValidationError as error:
            raise CausalValidationError(str(error)) from error

    def analyze(self, request: Mapping[str, object]) -> AnalysisResult:
        try:
            return self._analyze_intervention(request)
        except CausalValidationError:
            raise
        except DiscreteBayesValidationError as error:
            raise CausalValidationError(str(error)) from error

    def _analyze_intervention(self, request: Mapping[str, object]) -> AnalysisResult:
        if not isinstance(request, Mapping):
            raise CausalValidationError("request must be an object")
        require_only_fields(
            request, REQUEST_FIELDS, label="request", error_type=CausalValidationError
        )
        assumptions = self._assumptions(request.get("assumptions"))
        network = request.get("network")
        if isinstance(network, Mapping):
            variable_specs = network.get("variables")
            if isinstance(variable_specs, Mapping) and len(variable_specs) > MAX_VARIABLES:
                raise CausalValidationError(
                    f"network must contain at most {MAX_VARIABLES} variables"
                )

        # Validate the original graph and every CPT before removing any mechanism.
        # Otherwise an intervention could conceal a cycle or malformed treatment CPT.
        variables = self._network(network)
        query = self._query(request.get("query"), variables)
        evidence = self._evidence(request.get("evidence", {}), variables, label="evidence")
        interventions = self._evidence(
            request.get("interventions"), variables, label="interventions"
        )
        if not interventions:
            raise CausalValidationError("interventions must not be empty")

        intervened = dict(variables)
        for name, state in interventions.items():
            variable = variables[name]
            intervened[name] = Variable(
                name=name,
                states=variable.states,
                parents=(),
                cpt={(): {candidate: float(candidate == state) for candidate in variable.states}},
            )
        result = self._analyze_network(intervened, query, evidence)
        return AnalysisResult(
            engine=self.name,
            capabilities=self.capabilities,
            data=result.data,
            metadata=result.metadata
            | {
                "interventions": interventions,
                "evidence": evidence,
                "assumptions": assumptions,
                "method": "truncated_factorization",
                "interpretation": (
                    "Conditional on the supplied causal model and assumptions; "
                    "not identified from arbitrary datasets."
                ),
                "evidence_probability_semantics": "P(evidence | do(interventions))",
            },
        )

    @staticmethod
    def _assumptions(value: object) -> list[str]:
        if not isinstance(value, list) or not value:
            raise CausalValidationError("assumptions must be a non-empty list of strings")
        if len(value) > MAX_ASSUMPTIONS:
            raise CausalValidationError(f"assumptions must contain at most {MAX_ASSUMPTIONS} items")
        for assumption in value:
            if not isinstance(assumption, str) or not assumption.strip():
                raise CausalValidationError("assumptions must contain non-empty strings")
            if len(assumption) > MAX_ASSUMPTION_CHARS:
                raise CausalValidationError(
                    f"each assumption must contain at most {MAX_ASSUMPTION_CHARS} characters"
                )
        return list(value)

    def example_request(self) -> dict[str, object]:
        """Return a fresh request for an intervention on an explicit causal model."""
        request = super().example_request()
        request.update(
            query=["alarm"],
            evidence={},
            interventions={"fault": "present"},
            assumptions=[
                "Fault causally affects alarm, with no unmodeled common causes.",
                "The alarm mechanism is unchanged when fault is set by intervention.",
            ],
        )
        return request
