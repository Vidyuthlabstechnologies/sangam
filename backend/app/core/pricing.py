"""Sangamitra subscription plans and the 60/40 unit economics.

All money is integer paise. Plan prices are quoted EXCLUDING GST; the customer
pays price + 18% GST, and GST is passed to the government, so it never touches
the 60/40 split.

Split of the ex-GST price:
    60%  platform profit
    40%  provider pool (Sarvam + Vobiz DID + messaging)
         of which one month of DID rent comes off the top, and the rest buys
         call minutes at the raw Sarvam cost. Those minutes are credited to
         the customer's wallet at the retail rate (2.5x raw), in rupees.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

GST_RATE_PCT = 18
PLATFORM_PROFIT_PCT = 60
PROVIDER_POOL_PCT = 40

DID_MONTHLY_PAISE = 5900
RAW_COST_PER_MIN_PAISE = 300
RETAIL_RATE_PER_MIN_PAISE = 750  # 2.5x raw => 60% margin on usage

MIN_TOPUP_PAISE = 10_000      # Rs. 100
MAX_TOPUP_PAISE = 5_000_000   # Rs. 50,000


@dataclass(frozen=True)
class Plan:
    plan_id: str
    name: str
    audience: str
    price_paise: int            # ex-GST
    validity_days: int
    one_time: bool = False


PLANS: Dict[str, Plan] = {
    p.plan_id: p
    for p in (
        Plan("pilot", "7-Day Live Pilot", "Try it on a real number before committing", 79_900, 7, one_time=True),
        Plan("personal", "Mitra Personal", "Individuals, creators, founders", 99_900, 30),
        Plan("vyapar", "Vyapar Starter", "Shops, clinics, salons, small businesses", 249_900, 30),
        Plan("udyog", "Udyog B2B Pro", "Manufacturers, real estate, B2B sales desks", 499_900, 30),
        Plan("enterprise", "Enterprise", "Multi-branch and high call volume", 1_199_900, 30),
    )
}


def gst_paise(base_paise: int) -> int:
    return (base_paise * GST_RATE_PCT + 50) // 100


def total_with_gst_paise(base_paise: int) -> int:
    return base_paise + gst_paise(base_paise)


@dataclass(frozen=True)
class Split:
    base_paise: int
    gst_paise: int
    total_paise: int
    platform_profit_paise: int
    provider_pool_paise: int
    did_paise: int
    call_pool_paise: int          # provider cost budget for calls
    wallet_credit_paise: int      # retail value credited to the customer
    included_minutes: int


def split_plan(plan: Plan) -> Split:
    base = plan.price_paise
    profit = (base * PLATFORM_PROFIT_PCT + 50) // 100
    pool = base - profit
    call_pool = max(pool - DID_MONTHLY_PAISE, 0)
    credit = call_pool * RETAIL_RATE_PER_MIN_PAISE // RAW_COST_PER_MIN_PAISE
    return Split(
        base_paise=base,
        gst_paise=gst_paise(base),
        total_paise=total_with_gst_paise(base),
        platform_profit_paise=profit,
        provider_pool_paise=pool,
        did_paise=DID_MONTHLY_PAISE,
        call_pool_paise=call_pool,
        wallet_credit_paise=credit,
        included_minutes=call_pool // RAW_COST_PER_MIN_PAISE,
    )


def split_topup(base_paise: int) -> Split:
    profit = (base_paise * PLATFORM_PROFIT_PCT + 50) // 100
    pool = base_paise - profit
    return Split(
        base_paise=base_paise,
        gst_paise=gst_paise(base_paise),
        total_paise=total_with_gst_paise(base_paise),
        platform_profit_paise=profit,
        provider_pool_paise=pool,
        did_paise=0,
        call_pool_paise=pool,
        wallet_credit_paise=base_paise,
        included_minutes=base_paise // RETAIL_RATE_PER_MIN_PAISE,
    )


def call_debit_paise(duration_seconds: int) -> int:
    """Customer debit for a call, rounded UP to the next whole second's worth."""
    seconds = max(int(duration_seconds), 1)
    return (seconds * RETAIL_RATE_PER_MIN_PAISE + 59) // 60


def call_raw_cost_paise(duration_seconds: int) -> int:
    seconds = max(int(duration_seconds), 1)
    return (seconds * RAW_COST_PER_MIN_PAISE + 59) // 60


def plan_catalog() -> List[Dict]:
    out = []
    for plan in PLANS.values():
        s = split_plan(plan)
        out.append(
            {
                "plan_id": plan.plan_id,
                "name": plan.name,
                "audience": plan.audience,
                "validity_days": plan.validity_days,
                "one_time": plan.one_time,
                "price_inr": s.base_paise / 100,
                "gst_inr": s.gst_paise / 100,
                "total_payable_inr": s.total_paise / 100,
                "included_minutes": s.included_minutes,
                "wallet_credit_inr": s.wallet_credit_paise / 100,
                "overage_rate_per_min_inr": RETAIL_RATE_PER_MIN_PAISE / 100,
            }
        )
    return out


def get_plan(plan_id: str) -> Optional[Plan]:
    return PLANS.get((plan_id or "").strip().lower())
