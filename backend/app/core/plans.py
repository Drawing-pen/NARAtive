from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_pages: int | None
    monthly: int | None
    max_active: int | None


LIMITS = {
    "free": Limits(max_pages=50, monthly=3, max_active=3),
    "middle": Limits(max_pages=300, monthly=15, max_active=50),
    "high": Limits(max_pages=None, monthly=None, max_active=None),
}

PLAN_LABEL = {"free": "Standard", "middle": "Middle", "high": "High"}
UPGRADE_PRICE = {"middle": 29_000, "high": 59_000}
PERIOD_DAYS = 30
PAY_PER_CHECK_PRICE = 5_000
PAY_PER_CHECK_MAX = 10
BANKS = ("bca", "bni", "bri", "permata")
VA_TTL_HOURS = 24
