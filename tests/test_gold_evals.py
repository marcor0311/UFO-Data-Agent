"""Run the Gold evaluation set and certified queries on the real local snapshot.

Skipped when the generated Gold serving cache is absent (for example in CI,
which has no external data). The evaluation also records results per load_id.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SERVING = ROOT / "data/gold/serving/ufo_gold_serving.db"


@unittest.skipUnless(SERVING.exists(), "Gold serving cache not built locally")
class GoldEvaluationSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gold_query
        cls.analytics = gold_query.Analytics()

    def test_evaluation_set_passes_for_current_load(self):
        import run_gold_evals
        report = run_gold_evals.run(analytics=self.analytics)
        failed = [r for r in report["results"] if not r["passed"]]
        self.assertEqual(failed, [])
        self.assertTrue(report["summary"]["references_for_current_load"])
        self.assertGreaterEqual(report["summary"]["questions"], 50)

    def test_certified_queries_are_valid_and_reproduce(self):
        import gold_query
        for item in json.loads((ROOT / "config/gold/certified_queries.json").read_text())["queries"]:
            with self.subTest(item["id"]):
                self.assertTrue(self.analytics.certification_status(item)["valid"])
                result = self.analytics.run_certified(item["id"])
                self.assertEqual(result["result_type"], "certified")
                self.assertEqual(gold_query.rows_digest(result["rows"]), item["expected_result"]["rows_sha256"])


if __name__ == "__main__":
    unittest.main()
