"""Run the Gold evaluation set and certified queries on the real local snapshot.

Skipped when no Gold load is approved in the local catalog (for example in
CI, which has no external data). It opens the approved load exactly as the API
does and evaluates it with that load's own certified queries and references,
without writing anything.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import releases  # noqa: E402

APPROVED = releases.approved(releases.data_root(), "gold")


@unittest.skipUnless(APPROVED, "No approved Gold load in the local catalog")
class GoldEvaluationSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gold_query
        cls.analytics = gold_query.Analytics()

    def test_evaluation_set_passes_for_current_load(self):
        import run_gold_evals
        report = run_gold_evals.run(analytics=self.analytics, write=False)
        failed = [r for r in report["results"] if not r["passed"]]
        self.assertEqual(failed, [])
        self.assertTrue(report["summary"]["references_for_current_load"])
        self.assertGreaterEqual(report["summary"]["questions"], 50)

    def test_certified_queries_are_valid_and_reproduce(self):
        import gold_query
        self.assertEqual(self.analytics.coherence_problems(), [])
        for item in self.analytics.certified()["queries"]:
            with self.subTest(item["id"]):
                self.assertTrue(self.analytics.certification_status(item)["valid"])
                result = self.analytics.run_certified(item["id"])
                self.assertEqual(result["result_type"], "certified")
                self.assertEqual(gold_query.rows_digest(result["rows"]), item["expected_result"]["rows_sha256"])


if __name__ == "__main__":
    unittest.main()
