#!/usr/bin/env python3
"""Self-tests for wealth_math.py."""

import copy
import unittest

from wealth_math import DEFAULT_STRESS_SCENARIOS, EXAMPLE, calculate


class WealthMathTests(unittest.TestCase):
    def test_market_liquid_stock_is_not_runway(self):
        result = calculate(copy.deepcopy(EXAMPLE))
        self.assertEqual(result["market_liquid_assets"], 160000)
        self.assertEqual(result["safe_unearmarked_liquid_assets"], 50000)
        self.assertAlmostEqual(result["liquid_runway_months"], 6.25)

    def test_earmark_and_unfunded_payment_reduce_runway(self):
        data = copy.deepcopy(EXAMPLE)
        data["upcoming_payments"][0]["funded_amount"] = 4000
        result = calculate(data)
        self.assertEqual(result["unfunded_upcoming_payments"], 6000)
        self.assertEqual(result["safe_unearmarked_liquid_assets"], 44000)

    def test_candidate_income_is_excluded(self):
        result = calculate(copy.deepcopy(EXAMPLE))
        self.assertEqual(result["gross_monthly_income"], 13800)
        self.assertEqual(result["reliable_monthly_income"], 12500)
        self.assertEqual(result["reliable_sleep_income"], 500)

    def test_actual_expenses_reduce_actual_surplus(self):
        result = calculate(copy.deepcopy(EXAMPLE))
        self.assertEqual(result["safety_monthly_surplus"], 4500)
        self.assertEqual(result["actual_monthly_surplus"], 3000)

    def test_negative_surplus_and_negative_net_worth(self):
        data = copy.deepcopy(EXAMPLE)
        data["liabilities"][0]["value"] = 2000000
        data["monthly_expenses"][0]["amount"] = 20000
        data.pop("monthly_investable_surplus")
        result = calculate(data)
        self.assertLess(result["net_worth"], 0)
        self.assertLess(result["actual_monthly_surplus"], 0)
        self.assertIsNone(result["stress_tests"][0]["recovery_months"])

    def test_sector_extreme_shock_and_limit_breach(self):
        data = copy.deepcopy(EXAMPLE)
        data["assets"][2]["stress_bucket"] = "sector"
        result = calculate(data)
        extreme = next(item for item in result["stress_tests"] if item["name"] == "extreme")
        self.assertEqual(extreme["potential_loss"], 50000)
        self.assertIn("family_comfort_line", extreme["triggered_limits"])
        self.assertIn("personal_hard_loss_cap", extreme["triggered_limits"])

    def test_string_false_is_rejected(self):
        data = copy.deepcopy(EXAMPLE)
        data["assets"][0]["is_runway_eligible"] = "false"
        with self.assertRaises(ValueError):
            calculate(data)

    def test_missing_bucket_shock_is_rejected(self):
        data = copy.deepcopy(EXAMPLE)
        data["stress_scenarios"] = [{"name": "bad", "shocks": {"sector": 0.5}}]
        with self.assertRaises(ValueError):
            calculate(data)

    def test_missing_decision_pool_is_rejected(self):
        data = copy.deepcopy(EXAMPLE)
        del data["assets"][2]["decision_pool"]
        with self.assertRaises(ValueError):
            calculate(data)

    def test_earmarked_pool_is_not_runway(self):
        data = copy.deepcopy(EXAMPLE)
        data["assets"][0]["decision_pool"] = "earmarked"
        data["assets"][0]["earmarked_amount"] = 0
        result = calculate(data)
        self.assertEqual(result["gross_safe_liquid_assets"], 0)
        self.assertEqual(result["safe_unearmarked_liquid_assets"], 0)

    def test_risk_asset_cannot_be_runway_eligible(self):
        data = copy.deepcopy(EXAMPLE)
        data["assets"][2]["is_runway_eligible"] = True
        with self.assertRaises(ValueError):
            calculate(data)

    def test_nonfinancial_asset_cannot_be_financial_risk_asset(self):
        data = copy.deepcopy(EXAMPLE)
        data["assets"][3]["is_risk_asset"] = True
        data["assets"][3]["stress_bucket"] = "other"
        with self.assertRaises(ValueError):
            calculate(data)

    def test_scoped_limit_and_reached_status(self):
        data = copy.deepcopy(EXAMPLE)
        data["assets"][2]["decision_pool"] = "joint_authorized"
        data["risk_limits"] = [
            {"name": "personal", "amount": 1, "pools": ["individual_authorized"]},
            {"name": "joint", "amount": 40000, "pools": ["joint_authorized"]},
        ]
        result = calculate(data)
        extreme = next(item for item in result["stress_tests"] if item["name"] == "extreme")
        statuses = {item["name"]: item["status"] for item in extreme["limit_statuses"]}
        self.assertEqual(statuses["personal"], "below")
        self.assertEqual(statuses["joint"], "reached")

    def test_default_scenarios_cover_all_buckets(self):
        covered = set(DEFAULT_STRESS_SCENARIOS[0]["shocks"])
        self.assertEqual(
            covered, {"core_equity", "sector", "single_stock", "low_volatility", "other"}
        )


if __name__ == "__main__":
    unittest.main()
