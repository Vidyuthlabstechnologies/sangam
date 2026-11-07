"""Exact money handling for the payment path.

Amounts arrive as JSON numbers, i.e. binary floats. `int(amount * 100)`
truncates in floating point: 19.99 * 100 == 1998.9999999999998, so a Rs 19.99
order used to reach the gateway as 1998 paise. Everything sent to the gateway
goes through `to_minor_units`, which uses decimal arithmetic and refuses what
it cannot represent exactly instead of silently rounding it.

Storage is still `Float` in the models; moving to `Numeric` needs a migration
and is tracked separately. Values are validated here before they are stored.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

__all__ = ["InvalidAmount", "MAX_AMOUNT", "parse_amount", "to_minor_units"]

# A sanity bound against typos and overflow (Rs 100 crore), not a business limit.
MAX_AMOUNT = Decimal("1000000000")
_CENT = Decimal("0.01")


class InvalidAmount(ValueError):
    """The amount is not a positive, finite value with at most 2 decimals."""


def parse_amount(value: Any, *, allow_zero: bool = False) -> Decimal:
    """Return `value` as an exact 2-decimal Decimal, or raise InvalidAmount."""
    if value is None or isinstance(value, bool):
        raise InvalidAmount("Amount must be a number")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation:
        raise InvalidAmount("Amount must be a number") from None

    if not amount.is_finite():
        raise InvalidAmount("Amount must be a finite number")
    if amount < 0 or (amount == 0 and not allow_zero):
        raise InvalidAmount("Amount must be greater than zero")
    if amount > MAX_AMOUNT:
        raise InvalidAmount("Amount is too large")

    rounded = amount.quantize(_CENT)
    if rounded != amount:
        raise InvalidAmount("Amount cannot have more than 2 decimal places")
    return rounded


def to_minor_units(value: Any) -> int:
    """Rupees to paise, exactly."""
    return int(parse_amount(value) * 100)
