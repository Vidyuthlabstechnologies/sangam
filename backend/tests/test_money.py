"""Amounts must reach the gateway exactly, and bad amounts must never get there.

`int(amount * 100)` truncates in binary floating point: 19.99 * 100 is
1998.9999999999998, so a Rs 19.99 order was sent to the gateway as 1998 paise.
Nothing validated the amount either, so zero, negative and sub-paisa values
went straight through.
"""
from decimal import Decimal

import pytest

from app.core.money import InvalidAmount, to_minor_units
from app.core.payments import RazorpayService


@pytest.mark.parametrize(
    "amount,paise",
    [
        (19.99, 1999),
        (1.15, 115),
        (0.29, 29),
        (100, 10000),
        (250000.0, 25000000),
        ("10.50", 1050),
        (Decimal("0.01"), 1),
    ],
)
def test_to_minor_units_is_exact(amount, paise):
    assert to_minor_units(amount) == paise


def test_the_old_conversion_really_did_undercharge():
    assert int(19.99 * 100) == 1998
    assert to_minor_units(19.99) == 1999


@pytest.mark.parametrize(
    "bad",
    [0, -1, -0.01, float("nan"), float("inf"), 1.005, 0.001, "abc", "", None, True, 1e12],
)
def test_unrepresentable_or_unsafe_amounts_are_refused(bad):
    with pytest.raises(InvalidAmount):
        to_minor_units(bad)


@pytest.mark.asyncio
async def test_gateway_order_receives_exact_paise():
    order = await RazorpayService().create_order(amount=19.99, receipt="r-1")
    assert order["amount"] == 1999


@pytest.mark.asyncio
async def test_gateway_upi_order_receives_exact_paise():
    order = await RazorpayService().create_upi_intent_order(amount=1.15, receipt="r-2")
    assert order["amount"] == 115


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [0, -5])
async def test_initiate_rejects_non_positive_amounts(client, auth_headers, owned_workflow, amount):
    resp = await client.post(
        "/payments/initiate",
        json={"workflow_id": str(owned_workflow.id), "amount": amount},
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_initiate_rejects_sub_paisa_amounts(client, auth_headers, owned_workflow):
    resp = await client.post(
        "/payments/initiate",
        json={"workflow_id": str(owned_workflow.id), "amount": 10.005},
        headers=auth_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "decimal" in resp.json()["detail"].lower()
