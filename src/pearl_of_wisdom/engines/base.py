"""Shared expression helpers for engine implementations."""

from __future__ import annotations

import ast
import math

from .protocol import AnalysisResult

ALLOWED_BINARY_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
ALLOWED_UNARY_OPERATORS = (ast.UAdd, ast.USub)
MAX_EXPRESSION_CHARS = 4096
MAX_EXPRESSION_NODES = 256
__all__ = ["AnalysisResult", "compile_numeric_expression", "evaluate_numeric_expression"]


def compile_numeric_expression(expression: str) -> ast.Expression:
    """Compile a bounded numeric expression for repeated evaluation."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression must be a non-empty string")
    if len(expression) > MAX_EXPRESSION_CHARS:
        raise ValueError(f"expression must be at most {MAX_EXPRESSION_CHARS} characters")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError("expression must be valid Python arithmetic") from error

    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_EXPRESSION_NODES:
        raise ValueError(f"expression must contain at most {MAX_EXPRESSION_NODES} syntax nodes")
    for node in nodes:
        if isinstance(node, ast.Expression | ast.Load | ast.operator | ast.unaryop):
            continue
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, ALLOWED_BINARY_OPERATORS):
                raise ValueError("expression uses an unsupported operator")
            continue
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, ALLOWED_UNARY_OPERATORS):
                raise ValueError("expression uses an unsupported unary operator")
            continue
        if isinstance(node, ast.Name):
            continue
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, int | float):
                raise ValueError("expression constants must be numeric")
            continue
        raise ValueError("expression must contain only arithmetic on named variables")
    return tree


def evaluate_numeric_expression(compiled: ast.Expression, variables: dict[str, float]) -> float:
    """Evaluate a previously-validated arithmetic expression."""
    for node in ast.walk(compiled):
        if isinstance(node, ast.Name) and node.id not in variables:
            raise ValueError(f"expression references unknown variable {node.id!r}")
    try:
        value = eval(
            compile(compiled, "<pearl-expression>", "eval"),
            {"__builtins__": {}},
            variables,
        )
    except ArithmeticError as error:
        raise ValueError(f"expression evaluation failed: {error}") from error
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("expression must evaluate to a numeric result")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("expression must evaluate to a finite numeric result") from error
    if not math.isfinite(result):
        raise ValueError("expression must evaluate to a finite numeric result")
    return result
