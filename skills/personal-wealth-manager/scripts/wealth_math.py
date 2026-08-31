#!/usr/bin/env python3
"""Deterministic cash-flow, liquidity, and portfolio-stress arithmetic.

Run:
  python3 wealth_math.py example
  python3 wealth_math.py summary INPUT.json --format markdown
  python3 test_wealth_math.py

All amounts must already use one base currency. Keep the original currency and
exchange-rate date in the user's ledger. This script supports arithmetic; it
does not recommend investments.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


DECISION_POOLS = {
    "individual_authorized",
    "joint_authorized",
    "joint_unresolved",
    "earmarked",
}
INCOME_KINDS = {"active", "semi_active", "sleep", "occasional"}
INCOME_STATUSES = {"confirmed", "variable", "candidate"}
STRESS_BUCKETS = {"core_equity", "sector", "single_stock", "low_volatility", "other"}
AUTHORIZED_POOLS = {"individual_authorized", "joint_authorized"}

DEFAULT_STRESS_SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "ordinary",
        "shocks": {
            "core_equity": 0.10,
            "sector": 0.20,
            "single_stock": 0.20,
            "low_volatility": 0.05,
            "other": 0.10,
        },
    },
    {
        "name": "severe",
        "shocks": {
            "core_equity": 0.30,
            "sector": 0.40,
            "single_stock": 0.40,
            "low_volatility": 0.10,
            "other": 0.30,
        },
    },
    {
        "name": "extreme",
        "shocks": {
            "core_equity": 0.40,
            "sector": 0.50,
            "single_stock": 0.60,
            "low_volatility": 0.20,
            "other": 0.50,
        },
    },
]

EXAMPLE: dict[str, Any] = {
    "base_currency": "CNY",
    "assets": [
        {
            "name": "safe liquid cash",
            "value": 60000,
            "earmarked_amount": 10000,
            "is_financial": True,
            "is_market_liquid": True,
            "is_runway_eligible": True,
            "is_risk_asset": False,
            "decision_pool": "individual_authorized",
        },
        {
            "name": "term deposit",
            "value": 200000,
            "earmarked_amount": 0,
            "is_financial": True,
            "is_market_liquid": False,
            "is_runway_eligible": False,
            "is_risk_asset": False,
            "decision_pool": "individual_authorized",
        },
        {
            "name": "diversified equity core",
            "value": 100000,
            "earmarked_amount": 0,
            "is_financial": True,
            "is_market_liquid": True,
            "is_runway_eligible": False,
            "is_risk_asset": True,
            "decision_pool": "individual_authorized",
            "stress_bucket": "core_equity",
        },
        {
            "name": "home estimate",
            "value": 1000000,
            "earmarked_amount": 0,
            "is_financial": False,
            "is_market_liquid": False,
            "is_runway_eligible": False,
            "is_risk_asset": False,
            "decision_pool": "individual_authorized",
        },
    ],
    "liabilities": [{"name": "remaining loan", "value": 50000}],
    "monthly_income": [
        {"name": "salary", "amount": 12000, "kind": "active", "status": "confirmed"},
        {
            "name": "existing royalty income",
            "amount": 800,
            "conservative_amount": 500,
            "kind": "sleep",
            "status": "variable",
        },
        {"name": "unconfirmed variable income", "amount": 1000, "kind": "semi_active", "status": "candidate"},
    ],
    "monthly_expenses": [
        {"name": "necessary living", "amount": 7000, "necessary": True},
        {"name": "annual bills provision", "amount": 1000, "necessary": True},
        {"name": "discretionary", "amount": 1500, "necessary": False},
    ],
    "monthly_investable_surplus": 1200,
    "upcoming_payments": [
        {"name": "known annual bill", "amount": 10000, "funded_amount": 10000, "months_until_due": 4}
    ],
    "risk_limits": [
        {
            "name": "personal_hard_loss_cap",
            "amount": 40000,
            "pools": ["individual_authorized"],
        },
        {
            "name": "family_comfort_line",
            "amount": 30000,
            "pools": ["individual_authorized", "joint_authorized", "joint_unresolved"],
        },
    ],
    "stress_scenarios": DEFAULT_STRESS_SCENARIOS,
}


def require_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{path} must be finite and non-negative")
    return result


def require_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{path} must be true or false")
    return value


def require_choice(value: Any, choices: set[str], path: str) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{path} must be one of: {', '.join(sorted(choices))}")
    return value


def require_list(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{key}[{index}] must be an object")
    return value


def ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else None


def validated_assets(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for i, item in enumerate(require_list(data, "assets")):
        prefix = f"assets[{i}]"
        value = require_number(item.get("value", 0), f"{prefix}.value")
        earmarked = require_number(item.get("earmarked_amount", 0), f"{prefix}.earmarked_amount")
        if earmarked > value:
            raise ValueError(f"{prefix}.earmarked_amount cannot exceed value")
        asset = {
            "name": str(item.get("name", f"asset {i + 1}")),
            "value": value,
            "earmarked_amount": earmarked,
            "is_financial": require_bool(item.get("is_financial", False), f"{prefix}.is_financial"),
            "is_market_liquid": require_bool(
                item.get("is_market_liquid", False), f"{prefix}.is_market_liquid"
            ),
            "is_runway_eligible": require_bool(
                item.get("is_runway_eligible", False), f"{prefix}.is_runway_eligible"
            ),
            "is_risk_asset": require_bool(item.get("is_risk_asset", False), f"{prefix}.is_risk_asset"),
            "decision_pool": require_choice(
                item.get("decision_pool"),
                DECISION_POOLS,
                f"{prefix}.decision_pool",
            ),
        }
        if asset["is_runway_eligible"] and not asset["is_financial"]:
            raise ValueError(f"{prefix} cannot be runway-eligible unless it is financial")
        if asset["is_runway_eligible"] and asset["is_risk_asset"]:
            raise ValueError(f"{prefix} cannot be both runway-eligible and a risk asset")
        if asset["is_risk_asset"] and not asset["is_financial"]:
            raise ValueError(f"{prefix} cannot be a risk asset unless it is financial")
        if asset["is_risk_asset"]:
            asset["stress_bucket"] = require_choice(
                item.get("stress_bucket"), STRESS_BUCKETS, f"{prefix}.stress_bucket"
            )
        else:
            asset["stress_bucket"] = None
        result.append(asset)
    return result


def validated_income(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for i, item in enumerate(require_list(data, "monthly_income")):
        prefix = f"monthly_income[{i}]"
        amount = require_number(item.get("amount", 0), f"{prefix}.amount")
        kind = require_choice(item.get("kind"), INCOME_KINDS, f"{prefix}.kind")
        status = require_choice(item.get("status"), INCOME_STATUSES, f"{prefix}.status")
        conservative_raw = item.get("conservative_amount")
        if status == "variable":
            if conservative_raw is None:
                raise ValueError(f"{prefix}.conservative_amount is required for variable income")
            counted = require_number(conservative_raw, f"{prefix}.conservative_amount")
            if counted > amount:
                raise ValueError(f"{prefix}.conservative_amount cannot exceed amount")
        elif status == "candidate" or kind == "occasional":
            if conservative_raw not in (None, 0, 0.0):
                raise ValueError(f"{prefix} candidate or occasional income cannot be counted as reliable")
            counted = 0.0
        else:
            counted = amount
        result.append(
            {
                "name": str(item.get("name", f"income {i + 1}")),
                "amount": amount,
                "kind": kind,
                "status": status,
                "counted_amount": counted,
            }
        )
    return result


def validated_expenses(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for i, item in enumerate(require_list(data, "monthly_expenses")):
        prefix = f"monthly_expenses[{i}]"
        result.append(
            {
                "name": str(item.get("name", f"expense {i + 1}")),
                "amount": require_number(item.get("amount", 0), f"{prefix}.amount"),
                "necessary": require_bool(item.get("necessary", False), f"{prefix}.necessary"),
            }
        )
    return result


def validated_payments(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for i, item in enumerate(require_list(data, "upcoming_payments")):
        prefix = f"upcoming_payments[{i}]"
        amount = require_number(item.get("amount", 0), f"{prefix}.amount")
        funded = require_number(item.get("funded_amount", 0), f"{prefix}.funded_amount")
        if funded > amount:
            raise ValueError(f"{prefix}.funded_amount cannot exceed amount")
        result.append(
            {
                "name": str(item.get("name", f"payment {i + 1}")),
                "amount": amount,
                "funded_amount": funded,
                "months_until_due": require_number(
                    item.get("months_until_due", 0), f"{prefix}.months_until_due"
                ),
            }
        )
    return result


def validated_scenarios(data: dict[str, Any], used_buckets: set[str]) -> list[dict[str, Any]]:
    raw = data.get("stress_scenarios", DEFAULT_STRESS_SCENARIOS)
    if not isinstance(raw, list) or not raw:
        raise ValueError("stress_scenarios must be a non-empty list")
    result = []
    for i, scenario in enumerate(raw):
        if not isinstance(scenario, dict):
            raise ValueError(f"stress_scenarios[{i}] must be an object")
        name = str(scenario.get("name", f"scenario {i + 1}"))
        shocks = scenario.get("shocks")
        if not isinstance(shocks, dict):
            raise ValueError(f"stress_scenarios[{i}].shocks must be an object")
        validated_shocks = {}
        for bucket in used_buckets:
            if bucket not in shocks:
                raise ValueError(f"stress_scenarios[{i}].shocks is missing {bucket}")
            rate = require_number(shocks[bucket], f"stress_scenarios[{i}].shocks.{bucket}")
            if rate > 1:
                raise ValueError(f"stress_scenarios[{i}].shocks.{bucket} must be between 0 and 1")
            validated_shocks[bucket] = rate
        result.append({"name": name, "shocks": validated_shocks})
    return result


def validated_limits(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("risk_limits", [])
    if not isinstance(raw, list):
        raise ValueError("risk_limits must be a list")
    result = []
    names = set()
    for i, item in enumerate(raw):
        prefix = f"risk_limits[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{prefix} must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{prefix}.name must be a non-empty string")
        if name in names:
            raise ValueError(f"{prefix}.name must be unique")
        names.add(name)
        pools = item.get("pools")
        if not isinstance(pools, list) or not pools:
            raise ValueError(f"{prefix}.pools must be a non-empty list")
        validated_pools = [
            require_choice(pool, DECISION_POOLS, f"{prefix}.pools[{j}]")
            for j, pool in enumerate(pools)
        ]
        result.append(
            {
                "name": name,
                "amount": require_number(item.get("amount"), f"{prefix}.amount"),
                "pools": validated_pools,
            }
        )
    return result


def calculate(data: dict[str, Any]) -> dict[str, Any]:
    assets = validated_assets(data)
    liabilities = require_list(data, "liabilities")
    incomes = validated_income(data)
    expenses = validated_expenses(data)
    payments = validated_payments(data)
    limits = validated_limits(data)

    total_liabilities = sum(
        require_number(item.get("value", 0), f"liabilities[{i}].value")
        for i, item in enumerate(liabilities)
    )
    gross_assets = sum(item["value"] for item in assets)
    financial_assets = sum(item["value"] for item in assets if item["is_financial"])
    market_liquid_assets = sum(item["value"] for item in assets if item["is_market_liquid"])
    risk_assets = sum(item["value"] for item in assets if item["is_risk_asset"])
    gross_safe_liquid = sum(
        item["value"]
        for item in assets
        if item["is_runway_eligible"] and item["decision_pool"] != "earmarked"
    )
    safe_liquid_earmarks = sum(
        item["earmarked_amount"]
        for item in assets
        if item["is_runway_eligible"] and item["decision_pool"] != "earmarked"
    )
    unfunded_upcoming = sum(item["amount"] - item["funded_amount"] for item in payments)
    safe_unearmarked_liquid = max(
        gross_safe_liquid - safe_liquid_earmarks - unfunded_upcoming, 0
    )

    pool_summary: dict[str, dict[str, float | None]] = {}
    for pool in sorted(DECISION_POOLS):
        pool_assets = [item for item in assets if item["decision_pool"] == pool and item["is_financial"]]
        gross = sum(item["value"] for item in pool_assets)
        unearmarked = sum(item["value"] - item["earmarked_amount"] for item in pool_assets)
        risky = sum(item["value"] for item in pool_assets if item["is_risk_asset"])
        pool_summary[pool] = {
            "financial_assets": gross,
            "unearmarked_assets": unearmarked,
            "risk_assets": risky,
            "risk_asset_ratio": ratio(risky, unearmarked),
        }

    authorized_investable_assets = sum(
        item["value"] - item["earmarked_amount"]
        for item in assets
        if item["is_financial"] and item["decision_pool"] in AUTHORIZED_POOLS
    )
    authorized_risk_assets = sum(
        item["value"]
        for item in assets
        if item["is_risk_asset"] and item["decision_pool"] in AUTHORIZED_POOLS
    )

    gross_income = sum(item["amount"] for item in incomes)
    reliable_income = sum(item["counted_amount"] for item in incomes)
    reliable_sleep_income = sum(
        item["counted_amount"] for item in incomes if item["kind"] == "sleep"
    )
    necessary_expenses = sum(item["amount"] for item in expenses if item["necessary"])
    actual_expenses = sum(item["amount"] for item in expenses)
    safety_surplus = reliable_income - necessary_expenses
    actual_surplus = reliable_income - actual_expenses

    investable_raw = data.get("monthly_investable_surplus")
    if investable_raw is None:
        investable_surplus = None
    else:
        investable_surplus = require_number(investable_raw, "monthly_investable_surplus")
        if investable_surplus > max(actual_surplus, 0):
            raise ValueError("monthly_investable_surplus cannot exceed positive actual monthly surplus")

    used_buckets = {
        item["stress_bucket"] for item in assets if item["is_risk_asset"]
    }
    scenarios = validated_scenarios(data, used_buckets)
    stresses = []
    for scenario in scenarios:
        loss = 0.0
        loss_by_pool = {pool: 0.0 for pool in DECISION_POOLS}
        for item in assets:
            if not item["is_risk_asset"]:
                continue
            item_loss = item["value"] * scenario["shocks"][item["stress_bucket"]]
            loss += item_loss
            loss_by_pool[item["decision_pool"]] += item_loss
        limit_statuses = []
        for limit in limits:
            scoped_loss = sum(loss_by_pool[pool] for pool in limit["pools"])
            if scoped_loss > limit["amount"]:
                status = "breached"
            elif scoped_loss == limit["amount"]:
                status = "reached"
            else:
                status = "below"
            limit_statuses.append(
                {
                    "name": limit["name"],
                    "amount": limit["amount"],
                    "pools": limit["pools"],
                    "scoped_loss": scoped_loss,
                    "status": status,
                }
            )
        recovery_months = (
            loss / investable_surplus if investable_surplus is not None and investable_surplus > 0 else None
        )
        stresses.append(
            {
                "name": scenario["name"],
                "potential_loss": loss,
                "loss_as_financial_assets": ratio(loss, financial_assets),
                "loss_as_net_worth": ratio(loss, gross_assets - total_liabilities),
                "recovery_months": recovery_months,
                "loss_by_pool": loss_by_pool,
                "limit_statuses": limit_statuses,
                "triggered_limits": [
                    item["name"] for item in limit_statuses if item["status"] in {"reached", "breached"}
                ],
            }
        )

    return {
        "base_currency": data.get("base_currency", "BASE"),
        "gross_assets": gross_assets,
        "financial_assets": financial_assets,
        "market_liquid_assets": market_liquid_assets,
        "gross_safe_liquid_assets": gross_safe_liquid,
        "safe_unearmarked_liquid_assets": safe_unearmarked_liquid,
        "risk_assets": risk_assets,
        "liabilities": total_liabilities,
        "net_worth": gross_assets - total_liabilities,
        "upcoming_payments": sum(item["amount"] for item in payments),
        "unfunded_upcoming_payments": unfunded_upcoming,
        "gross_monthly_income": gross_income,
        "reliable_monthly_income": reliable_income,
        "reliable_sleep_income": reliable_sleep_income,
        "necessary_monthly_expenses": necessary_expenses,
        "actual_monthly_expenses": actual_expenses,
        "safety_monthly_surplus": safety_surplus,
        "actual_monthly_surplus": actual_surplus,
        "monthly_investable_surplus": investable_surplus,
        "liquid_runway_months": ratio(safe_unearmarked_liquid, necessary_expenses),
        "income_coverage": ratio(reliable_income, necessary_expenses),
        "sleep_income_coverage": ratio(reliable_sleep_income, necessary_expenses),
        "risk_asset_ratio_financial": ratio(risk_assets, financial_assets),
        "risk_asset_ratio_net_worth": ratio(risk_assets, gross_assets - total_liabilities),
        "authorized_investable_assets": authorized_investable_assets,
        "authorized_risk_assets": authorized_risk_assets,
        "risk_asset_ratio_authorized_pool": ratio(
            authorized_risk_assets, authorized_investable_assets
        ),
        "decision_pools": pool_summary,
        "risk_limits": limits,
        "stress_tests": stresses,
        "notes": [
            "Market-liquid assets and runway-eligible assets are different.",
            "Runway excludes asset earmarks and unfunded upcoming payments.",
            "Candidate and occasional income do not enter reliable income.",
            "Recovery time uses the user-authorized investable surplus only.",
            "Stress tests use asset-bucket shocks stated in the input.",
            "Results are arithmetic support, not investment advice.",
        ],
    }


def money(value: float | None, currency: str) -> str:
    return "n/a" if value is None else f"{currency} {value:,.2f}"


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def number(value: float | None, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value:,.1f}{suffix}"


def to_markdown(result: dict[str, Any]) -> str:
    ccy = result["base_currency"]
    lines = [
        "# Wealth arithmetic summary",
        "",
        f"- Gross assets: {money(result['gross_assets'], ccy)}",
        f"- Financial assets: {money(result['financial_assets'], ccy)}",
        f"- Market-liquid assets: {money(result['market_liquid_assets'], ccy)}",
        f"- Safe unearmarked liquid assets: {money(result['safe_unearmarked_liquid_assets'], ccy)}",
        f"- Unfunded upcoming payments: {money(result['unfunded_upcoming_payments'], ccy)}",
        f"- Risk assets: {money(result['risk_assets'], ccy)}",
        f"- Liabilities: {money(result['liabilities'], ccy)}",
        f"- Net worth: {money(result['net_worth'], ccy)}",
        f"- Reliable monthly income: {money(result['reliable_monthly_income'], ccy)}",
        f"- Reliable sleep income: {money(result['reliable_sleep_income'], ccy)}",
        f"- Necessary monthly expenses: {money(result['necessary_monthly_expenses'], ccy)}",
        f"- Actual monthly expenses: {money(result['actual_monthly_expenses'], ccy)}",
        f"- Safety monthly surplus: {money(result['safety_monthly_surplus'], ccy)}",
        f"- Actual monthly surplus: {money(result['actual_monthly_surplus'], ccy)}",
        f"- Authorized investable monthly surplus: {money(result['monthly_investable_surplus'], ccy)}",
        f"- Liquid runway: {number(result['liquid_runway_months'], ' months')}",
        f"- Sleep-income coverage: {percent(result['sleep_income_coverage'])}",
        f"- Risk assets / financial assets: {percent(result['risk_asset_ratio_financial'])}",
        f"- Risk assets / net worth: {percent(result['risk_asset_ratio_net_worth'])}",
        f"- Risk assets / authorized pool: {percent(result['risk_asset_ratio_authorized_pool'])}",
        "",
        "## Decision pools",
        "",
        "| Pool | Financial assets | Unearmarked assets | Risk assets | Risk ratio |",
        "|---|---:|---:|---:|---:|",
    ]
    for pool, item in result["decision_pools"].items():
        lines.append(
            "| "
            + " | ".join(
                [
                    pool,
                    money(item["financial_assets"], ccy),
                    money(item["unearmarked_assets"], ccy),
                    money(item["risk_assets"], ccy),
                    percent(item["risk_asset_ratio"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
        "",
        "## Stress tests",
        "",
        "| Scenario | Potential loss | Loss by pool | % financial assets | % net worth | Recovery months | Reached/breached limits |",
        "|---|---:|---|---:|---:|---:|---|",
        ]
    )
    for item in result["stress_tests"]:
        loss_by_pool = ", ".join(
            f"{pool}={money(loss, ccy)}"
            for pool, loss in item["loss_by_pool"].items()
            if loss > 0
        ) or "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    item["name"],
                    money(item["potential_loss"], ccy),
                    loss_by_pool,
                    percent(item["loss_as_financial_assets"]),
                    percent(item["loss_as_net_worth"]),
                    number(item["recovery_months"]),
                    ", ".join(item["triggered_limits"]) or "none",
                ]
            )
            + " |"
        )
    lines.extend(["", "_Arithmetic support only; not an investment recommendation._"])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("example", help="print an example input JSON")
    summary = subparsers.add_parser("summary", help="calculate a wealth summary")
    summary.add_argument("input", type=Path, help="JSON input path")
    summary.add_argument("--format", choices=["json", "markdown"], default="json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "example":
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return 0

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("input root must be an object")
        result = calculate(data)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "markdown":
        print(to_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
