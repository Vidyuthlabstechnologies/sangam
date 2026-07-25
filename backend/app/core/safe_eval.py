"""Evaluate workflow conditions without executing arbitrary code.

Workflow conditions arrive from API payloads and templates: they are
attacker-influenced data. The previous implementation ran them through
``eval(condition, {"__builtins__": {}}, context)``. Emptying ``__builtins__``
is not a sandbox — any literal exposes ``__class__``, and from there
``().__class__.__bases__[0].__subclasses__()`` walks to arbitrary imports.

This module instead parses to an AST and walks it with an explicit allowlist
of node types. Anything not on the list raises rather than executing, so the
failure mode is a rejected condition instead of code execution.
"""
from __future__ import annotations

import ast
import operator
from typing import Any, Dict

__all__ = ["safe_evaluate", "UnsafeExpressionError"]


class UnsafeExpressionError(ValueError):
    """Raised when an expression uses constructs outside the allowlist."""


class _Missing:
    """Sentinel for a name absent from the evaluation context."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<missing>"


_MISSING = _Missing()

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

_ALLOWED_NODES: tuple = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.BinOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
) + tuple(_BIN_OPS) + tuple(_CMP_OPS)


class _Evaluator(ast.NodeVisitor):
    def __init__(self, context: Dict[str, Any]) -> None:
        self.context = context

    def visit(self, node: ast.AST) -> Any:
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeExpressionError(
                f"Disallowed expression element: {type(node).__name__}"
            )
        return super().visit(node)

    def generic_visit(self, node: ast.AST) -> Any:
        raise UnsafeExpressionError(
            f"Disallowed expression element: {type(node).__name__}"
        )

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        return self.context.get(node.id, _MISSING)

    def visit_List(self, node: ast.List) -> Any:
        return [self.visit(e) for e in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        return tuple(self.visit(e) for e in node.elts)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            if operand is _MISSING:
                return _MISSING
            return -operand
        raise UnsafeExpressionError(
            f"Disallowed unary operator: {type(node.op).__name__}"
        )

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        values = [self.visit(v) for v in node.values]
        normalised = [False if v is _MISSING else v for v in values]
        if isinstance(node.op, ast.And):
            return all(normalised)
        return any(normalised)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        fn = _BIN_OPS.get(type(node.op))
        if fn is None:
            raise UnsafeExpressionError(
                f"Disallowed operator: {type(node.op).__name__}"
            )
        left, right = self.visit(node.left), self.visit(node.right)
        if left is _MISSING or right is _MISSING:
            return _MISSING
        try:
            return fn(left, right)
        except (TypeError, ZeroDivisionError):
            return _MISSING

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            fn = _CMP_OPS.get(type(op))
            if fn is None:
                raise UnsafeExpressionError(
                    f"Disallowed comparison: {type(op).__name__}"
                )
            right = self.visit(comparator)
            if left is _MISSING or right is _MISSING:
                return False
            try:
                if not fn(left, right):
                    return False
            except TypeError:
                return False
            left = right
        return True


def safe_evaluate(condition: str, context: Dict[str, Any]) -> bool:
    """Evaluate a workflow condition against ``context``.

    An empty condition is True (no gate). Names absent from ``context``
    evaluate falsey rather than raising, so a condition referencing workflow
    data that has not been populated yet degrades to False instead of a 500.

    Raises:
        UnsafeExpressionError: the expression is malformed, or uses a
            construct outside the allowlist.
    """
    if not condition or not condition.strip():
        return True

    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Invalid condition syntax: {exc}") from exc

    result = _Evaluator(context).visit(tree)
    if result is _MISSING:
        return False
    return bool(result)
