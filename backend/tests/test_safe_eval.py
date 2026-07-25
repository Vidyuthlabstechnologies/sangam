"""Workflow conditions are attacker-influenced data, not trusted code.

The previous implementation called eval() with {"__builtins__": {}}, which
is not a sandbox — attribute traversal from any literal reaches the object
graph and from there the interpreter.
"""
import pytest

from app.core.safe_eval import safe_evaluate, UnsafeExpressionError


class TestLegitimateConditions:
    def test_simple_comparison(self):
        assert safe_evaluate("amount > 100", {"amount": 500}) is True
        assert safe_evaluate("amount > 100", {"amount": 50}) is False

    def test_boolean_logic(self):
        ctx = {"approved": True, "amount": 5000}
        assert safe_evaluate("approved and amount < 10000", ctx) is True
        assert safe_evaluate("approved and amount > 10000", ctx) is False

    def test_or_and_not(self):
        ctx = {"urgent": False, "escalated": True}
        assert safe_evaluate("urgent or escalated", ctx) is True
        assert safe_evaluate("not urgent", ctx) is True

    def test_equality_and_membership(self):
        ctx = {"status": "qualified", "tags": ["cdsco", "gmp"]}
        assert safe_evaluate("status == 'qualified'", ctx) is True
        assert safe_evaluate("status != 'rejected'", ctx) is True
        assert safe_evaluate("'gmp' in tags", ctx) is True
        assert safe_evaluate("'iso' in tags", ctx) is False

    def test_arithmetic(self):
        assert safe_evaluate("qty * price > 1000", {"qty": 20, "price": 60}) is True

    def test_chained_comparison(self):
        assert safe_evaluate("0 < score < 100", {"score": 55}) is True
        assert safe_evaluate("0 < score < 100", {"score": 150}) is False


class TestDegradation:
    def test_missing_variable_is_false_not_crash(self):
        assert safe_evaluate("nonexistent > 5", {}) is False

    def test_empty_condition_is_true(self):
        assert safe_evaluate("", {}) is True
        assert safe_evaluate("   ", {}) is True

    def test_invalid_syntax_raises_unsafe(self):
        with pytest.raises(UnsafeExpressionError):
            safe_evaluate("amount >", {"amount": 1})


class TestRejectsCodeExecution:
    @pytest.mark.parametrize("attack", [
        "__import__('os').system('echo pwned')",
        "().__class__.__bases__[0].__subclasses__()",
        "open('/etc/passwd').read()",
        "lambda: 1",
        "[x for x in range(10)]",
        "exec('x=1')",
        "globals()",
        "(1).__class__",
        "{'a': 1}.keys()",
    ])
    def test_rejects(self, attack):
        with pytest.raises(UnsafeExpressionError):
            safe_evaluate(attack, {})

    def test_old_eval_sandbox_escape_is_blocked(self):
        """The classic escape that {"__builtins__": {}} does not stop."""
        escape = "().__class__.__bases__[0].__subclasses__()"
        with pytest.raises(UnsafeExpressionError):
            safe_evaluate(escape, {})
