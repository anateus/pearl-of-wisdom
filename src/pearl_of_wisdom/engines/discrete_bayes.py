"""Exact discrete Bayesian inference by joint enumeration."""

from __future__ import annotations

import itertools
import math
import sys
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from .base import require_only_fields
from .protocol import AnalysisResult

REQUEST_FIELDS = {"evidence", "network", "query"}
NETWORK_FIELDS = {"variables"}
VARIABLE_FIELDS = {"cpt", "parents", "states"}
CPT_ROW_FIELDS = {"probabilities", "when"}


class DiscreteBayesValidationError(ValueError):
    """Raised when a discrete Bayes network or query is invalid."""


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    states: tuple[str, ...]
    parents: tuple[str, ...]
    cpt: dict[tuple[str, ...], dict[str, float]]


def _require_mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DiscreteBayesValidationError(f"{label} must be an object")
    return value


def _require_probability(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DiscreteBayesValidationError(f"{label} must be numeric")
    try:
        probability = float(value)
    except OverflowError as error:
        raise DiscreteBayesValidationError(f"{label} must be between 0 and 1") from error
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise DiscreteBayesValidationError(f"{label} must be between 0 and 1")
    return probability


class DiscreteBayesEngine:
    """Compute exact posteriors for small discrete Bayesian networks."""

    name = "discrete_bayes"
    capabilities = ("inference.discrete_bayes", "uncertainty.hypotheses")

    def __init__(self, *, max_states: int = 4096) -> None:
        if isinstance(max_states, bool) or not isinstance(max_states, int) or max_states < 1:
            raise DiscreteBayesValidationError("max_states must be a positive integer")
        self.max_states = max_states

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def analyze(self, request: dict[str, object]) -> AnalysisResult:
        request_map = _require_mapping(request, label="request")
        require_only_fields(
            request_map,
            REQUEST_FIELDS,
            label="request",
            error_type=DiscreteBayesValidationError,
        )
        variables = self._network(request_map.get("network"))
        query = self._query(request_map.get("query"), variables)
        evidence = self._evidence(request_map.get("evidence", {}), variables, label="evidence")
        return self._analyze_network(variables, query, evidence)

    def _analyze_network(
        self,
        variables: Mapping[str, Variable],
        query: tuple[str, ...],
        evidence: Mapping[str, str],
    ) -> AnalysisResult:
        """Enumerate a validated network, query, and evidence assignment."""
        order = self._topological_order(variables)
        assignments = self._joint_distribution(order, variables)
        evidence_probability = 0.0
        grouped: defaultdict[tuple[str, ...], float] = defaultdict(float)
        for assignment, probability in assignments:
            if self._matches(assignment, evidence):
                evidence_probability += probability
                grouped[tuple(assignment[name] for name in query)] += probability
        if evidence_probability == 0:
            raise DiscreteBayesValidationError("impossible evidence under the network")
        rows = []
        for state_tuple in itertools.product(*(variables[name].states for name in query)):
            probability = grouped.get(state_tuple, 0.0) / evidence_probability
            rows.append(
                {
                    "assignment": {
                        name: state for name, state in zip(query, state_tuple, strict=True)
                    },
                    "probability": probability,
                }
            )
        return AnalysisResult(
            engine=self.name,
            capabilities=self.capabilities,
            data={"distribution": rows, "evidence_probability": evidence_probability},
            metadata={"query": list(query), "variables": len(variables)},
        )

    def example_request(self) -> dict[str, object]:
        """Return a small request that exercises this engine's public input shape."""
        return {
            "network": {
                "variables": {
                    "fault": {
                        "states": ["present", "absent"],
                        "parents": [],
                        "cpt": [
                            {
                                "when": {},
                                "probabilities": {"present": 0.2, "absent": 0.8},
                            }
                        ],
                    },
                    "alarm": {
                        "states": ["positive", "negative"],
                        "parents": ["fault"],
                        "cpt": [
                            {
                                "when": {"fault": "present"},
                                "probabilities": {"positive": 0.8, "negative": 0.2},
                            },
                            {
                                "when": {"fault": "absent"},
                                "probabilities": {"positive": 0.1, "negative": 0.9},
                            },
                        ],
                    },
                }
            },
            "query": ["fault"],
            "evidence": {"alarm": "positive"},
        }

    def _network(self, value: object) -> dict[str, Variable]:
        network = _require_mapping(value, label="network")
        require_only_fields(
            network,
            NETWORK_FIELDS,
            label="network",
            error_type=DiscreteBayesValidationError,
        )
        variable_specs = _require_mapping(network.get("variables"), label="network.variables")
        if not variable_specs:
            raise DiscreteBayesValidationError("network.variables must not be empty")
        variables: dict[str, Variable] = {}
        for name, raw_spec in variable_specs.items():
            if not isinstance(name, str) or not name:
                raise DiscreteBayesValidationError("variable names must be non-empty strings")
            spec = _require_mapping(raw_spec, label=f"network.variables.{name}")
            require_only_fields(
                spec,
                VARIABLE_FIELDS,
                label=f"network.variables.{name}",
                error_type=DiscreteBayesValidationError,
            )
            states_raw = spec.get("states")
            if not isinstance(states_raw, list) or not states_raw:
                raise DiscreteBayesValidationError(
                    f"network.variables.{name}.states must be a list"
                )
            states = tuple(states_raw)
            if any(not isinstance(state, str) or not state for state in states):
                raise DiscreteBayesValidationError(
                    f"network.variables.{name}.states must be strings"
                )
            if len(set(states)) != len(states):
                raise DiscreteBayesValidationError(
                    f"network.variables.{name}.states must be unique"
                )
            parents_raw = spec.get("parents", [])
            if not isinstance(parents_raw, list):
                raise DiscreteBayesValidationError(
                    f"network.variables.{name}.parents must be a list"
                )
            parents = tuple(parents_raw)
            if any(not isinstance(parent, str) or not parent for parent in parents):
                raise DiscreteBayesValidationError(
                    f"network.variables.{name}.parents must be strings"
                )
            if len(set(parents)) != len(parents):
                raise DiscreteBayesValidationError(
                    f"network.variables.{name}.parents must be unique"
                )
            cpt_raw = spec.get("cpt")
            if not isinstance(cpt_raw, list) or not cpt_raw:
                raise DiscreteBayesValidationError(
                    f"network.variables.{name}.CPT must be a non-empty list"
                )
            variables[name] = Variable(name=name, states=states, parents=parents, cpt={})
        for variable in variables.values():
            for parent in variable.parents:
                if parent not in variables:
                    raise DiscreteBayesValidationError(
                        "network.variables."
                        f"{variable.name}.parents references unknown parent {parent!r}"
                    )
        self._check_state_space_limit(variables)
        order = self._topological_order(variables)
        del order
        hydrated: dict[str, Variable] = {}
        for name, variable in variables.items():
            hydrated[name] = Variable(
                name=name,
                states=variable.states,
                parents=variable.parents,
                cpt=self._cpt(variable, variable_specs[name], variables),
            )
        return hydrated

    def _cpt(
        self,
        variable: Variable,
        raw_spec: object,
        variables: Mapping[str, Variable],
    ) -> dict[tuple[str, ...], dict[str, float]]:
        spec = _require_mapping(raw_spec, label=f"network.variables.{variable.name}")
        rows = spec.get("cpt")
        assert isinstance(rows, list)
        expected_parent_keys = [
            tuple(state_tuple)
            for state_tuple in itertools.product(
                *(variables[parent].states for parent in variable.parents)
            )
        ]
        seen: dict[tuple[str, ...], dict[str, float]] = {}
        for index, row in enumerate(rows):
            row_map = _require_mapping(row, label=f"network.variables.{variable.name}.cpt[{index}]")
            require_only_fields(
                row_map,
                CPT_ROW_FIELDS,
                label=f"network.variables.{variable.name}.cpt[{index}]",
                error_type=DiscreteBayesValidationError,
            )
            when = _require_mapping(
                row_map.get("when", {}),
                label=f"network.variables.{variable.name}.cpt[{index}].when",
            )
            probabilities = _require_mapping(
                row_map.get("probabilities"),
                label=f"network.variables.{variable.name}.cpt[{index}].probabilities",
            )
            if set(when) != set(variable.parents):
                raise DiscreteBayesValidationError(
                    f"network.variables.{variable.name}.CPT must define every parent state in when"
                )
            parent_states: list[str] = []
            for parent in variable.parents:
                state = when[parent]
                if not isinstance(state, str) or state not in variables[parent].states:
                    raise DiscreteBayesValidationError(
                        f"network.variables.{variable.name}.cpt[{index}] has invalid parent state"
                    )
                parent_states.append(state)
            if set(probabilities) != set(variable.states):
                raise DiscreteBayesValidationError(
                    f"network.variables.{variable.name}.CPT[{index}] must include every state"
                )
            distribution = {
                state: _require_probability(
                    probabilities[state],
                    label=f"network.variables.{variable.name}.cpt[{index}].probabilities.{state}",
                )
                for state in variable.states
            }
            if not math.isclose(sum(distribution.values()), 1.0, rel_tol=0, abs_tol=1e-9):
                raise DiscreteBayesValidationError(
                    f"network.variables.{variable.name}.CPT[{index}] probabilities must sum to 1"
                )
            key = tuple(parent_states)
            if key in seen:
                raise DiscreteBayesValidationError(
                    f"network.variables.{variable.name}.CPT duplicates a parent assignment"
                )
            seen[key] = distribution
        if set(seen) != set(expected_parent_keys):
            raise DiscreteBayesValidationError(
                f"network.variables.{variable.name}.CPT does not cover every parent assignment"
            )
        return seen

    def _query(
        self,
        value: object,
        variables: Mapping[str, Variable],
    ) -> tuple[str, ...]:
        if not isinstance(value, list) or not value:
            raise DiscreteBayesValidationError("query must be a non-empty list")
        query = tuple(value)
        if any(not isinstance(name, str) or name not in variables for name in query):
            raise DiscreteBayesValidationError("query contains an unknown variable")
        if len(set(query)) != len(query):
            raise DiscreteBayesValidationError("query must not repeat variables")
        return query

    def _evidence(
        self,
        value: object,
        variables: Mapping[str, Variable],
        *,
        label: str,
    ) -> dict[str, str]:
        mapping = _require_mapping(value, label=label)
        result: dict[str, str] = {}
        for name, state in mapping.items():
            if name not in variables:
                raise DiscreteBayesValidationError(f"{label} contains an unknown variable")
            if not isinstance(state, str) or state not in variables[name].states:
                raise DiscreteBayesValidationError(f"{label} contains an invalid state")
            result[name] = state
        return result

    def _topological_order(self, variables: Mapping[str, Variable]) -> tuple[str, ...]:
        temporary: set[str] = set()
        permanent: set[str] = set()
        ordered: list[str] = []

        def visit(name: str) -> None:
            if name in permanent:
                return
            if name in temporary:
                raise DiscreteBayesValidationError("network contains a cycle")
            temporary.add(name)
            for parent in variables[name].parents:
                visit(parent)
            temporary.remove(name)
            permanent.add(name)
            ordered.append(name)

        for name in variables:
            visit(name)
        return tuple(ordered)

    def _joint_distribution(
        self,
        order: tuple[str, ...],
        variables: Mapping[str, Variable],
    ) -> list[tuple[dict[str, str], float]]:
        assignments: list[tuple[dict[str, str], float]] = [({}, 1.0)]
        for name in order:
            variable = variables[name]
            next_assignments: list[tuple[dict[str, str], float]] = []
            for partial, partial_probability in assignments:
                parent_key = tuple(partial[parent] for parent in variable.parents)
                distribution = variable.cpt[parent_key]
                for state in variable.states:
                    probability = partial_probability * distribution[state]
                    if (
                        probability < sys.float_info.min
                        and partial_probability > 0
                        and distribution[state] > 0
                    ):
                        raise DiscreteBayesValidationError(
                            "joint probability underflow exceeds floating-point precision"
                        )
                    next_assignments.append((partial | {name: state}, probability))
            assignments = next_assignments
        return assignments

    def _check_state_space_limit(self, variables: Mapping[str, Variable]) -> None:
        state_space = 1
        for variable in variables.values():
            state_space *= len(variable.states)
            if state_space > self.max_states:
                raise DiscreteBayesValidationError(
                    f"state space {state_space} exceeds configured limit {self.max_states}"
                )

    @staticmethod
    def _matches(assignment: Mapping[str, str], evidence: Mapping[str, str]) -> bool:
        return all(assignment[name] == state for name, state in evidence.items())
