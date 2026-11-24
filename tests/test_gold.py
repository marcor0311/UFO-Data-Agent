"""Gold contract tests on synthetic Silver/Bronze fixtures (no external data)."""
from __future__ import annotations

from contextlib import closing
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gold_fixture import build_fixture, environment, fake_gate, serving_fixture, sha, write_provenance

import build_gold
import check_gold_ready
import gold_query
from gold_common import load_catalogs
from gold_query import QueryError


class GoldBuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_reconciles_and_publishes_manifest(self):
        manifest, policy, silver, bronze, output = build_fixture(self.folder)
        self.assertEqual(manifest["totals"]["reports"], 12)
        self.assertEqual(manifest["totals"]["confirmed_events"], 1)
        self.assertEqual(manifest["totals"]["pending_candidate_reports"], 4)   # reports 1, 2, 6, 10
        self.assertEqual(manifest["silver"]["sha256"], sha(silver))
        self.assertEqual(manifest["gold_sha256"], sha(output))
        self.assertFalse(output.with_name(output.name + ".building").exists())
        checks = check_gold_ready.model_checks(output, silver, bronze, policy, load_catalogs())
        self.assertEqual([c for c in checks if not c["passed"]], [])

    def test_eligibility_values_and_exclusions(self):
        *_, output = build_fixture(self.folder)
        with closing(sqlite3.connect(output)) as conn:
            rows = {r[0]: r[1:] for r in conn.execute("""SELECT report_id, event_date, weekday, event_hour, day_exclusion,
                month_exclusion, calendar_exclusion, date_key, cell1_lat, cell1_lng, distance_band, duplicate_status FROM fact_report""")}
        self.assertEqual(rows[1][:3], ("1997-03-13", 4, 20))          # Thursday 20:30
        self.assertEqual(rows[3][3], "day_placeholder")               # day 01 of a flagged source
        self.assertIsNone(rows[3][1])
        self.assertEqual(rows[5][4], "month_day_placeholder")        # 01-01 marker
        self.assertIsNone(rows[5][5])                                 # still apt for calendar
        self.assertEqual(rows[5][6], "2001")                          # date_key at year precision
        self.assertEqual(rows[8][5], "date_qualified")
        self.assertIsNone(rows[8][2])                                 # clock on a qualified date is not usable
        self.assertEqual(rows[9][5], "date_range")
        self.assertEqual(rows[10][7:9], (89, 179))                    # closing edge joins the last cell
        self.assertEqual(rows[10][9], "d1000_plus")
        self.assertEqual(rows[12][9], "d0010_0025")
        self.assertEqual(rows[1][10], "confirmed_canonical")
        self.assertEqual(rows[2][10], "confirmed_member")
        self.assertEqual(rows[6][10], "pending_candidate")

    def test_aggregates_and_bounds(self):
        *_, output = build_fixture(self.folder)
        with closing(sqlite3.connect(output)) as conn:
            total = conn.execute("SELECT SUM(report_count), SUM(report_count_excl_candidates), SUM(pending_candidate_reports) FROM agg_source").fetchone()
            self.assertEqual(total, (12, 8, 4))
            self.assertEqual(conn.execute("SELECT SUM(report_count) FROM agg_month").fetchone()[0],
                             conn.execute("SELECT COUNT(*) FROM fact_report WHERE usable_for_month_analysis=1").fetchone()[0])
            for (aggregate,) in conn.execute("SELECT DISTINCT aggregate_code FROM agg_coverage"):
                self.assertEqual(conn.execute("SELECT SUM(report_count) FROM agg_coverage WHERE aggregate_code=?", (aggregate,)).fetchone()[0], 12)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agg_year WHERE report_count_excl_candidates > report_count").fetchone()[0], 0)

    def refused(self, policy, silver, bronze, output, problem):
        with self.assertRaises(build_gold.GoldBuildError) as raised:
            build_gold.build(policy=policy, gate=fake_gate, silver_path=silver, bronze_path=bronze, output=output)
        self.assertIn(problem, str(raised.exception))
        self.assertFalse(output.exists())

    def test_rebuilt_silver_is_accepted_without_a_fixed_pin(self):
        policy, silver, bronze, output = environment(self.folder)
        self.assertNotIn("sha256", policy["inputs"]["silver"])
        manifest = build_gold.build(policy=policy, gate=fake_gate, silver_path=silver, bronze_path=bronze, output=output)
        self.assertEqual(manifest["silver"]["sha256"], sha(silver))
        self.assertEqual(len(manifest["silver_run_id"]), 64)

    def test_silver_modified_after_validation_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        with closing(sqlite3.connect(silver)) as conn:
            conn.execute("CREATE TABLE tampered (x)"); conn.commit()
        self.refused(policy, silver, bronze, output, "modificado o sustituido")

    def test_silver_without_validation_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        silver.with_suffix(".validation.json").unlink()
        self.refused(policy, silver, bronze, output, "falta o es ilegible")

    def test_failed_silver_validation_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        write_provenance(self.folder, policy, silver, bronze, passed=False)
        self.refused(policy, silver, bronze, output, "no fue aprobada")

    def test_silver_from_another_bronze_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        lineage = json.loads(silver.with_suffix(".validation.json").read_text())["lineage"]
        write_provenance(self.folder, policy, silver, bronze, lineage={**lineage, "bronze_sha256": "0" * 64})
        self.refused(policy, silver, bronze, output, "otra Bronze")

    def test_outdated_silver_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        lineage = json.loads(silver.with_suffix(".validation.json").read_text())["lineage"]
        write_provenance(self.folder, policy, silver, bronze, lineage={**lineage, "run_id": "1" * 64})
        self.refused(policy, silver, bronze, output, "desactualizada")

    def test_unofficial_bronze_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        Path(policy["inputs"]["bronze"]["manifest"]).write_text(json.dumps({"sha256": "0" * 64, "size_bytes": bronze.stat().st_size}))
        self.refused(policy, silver, bronze, output, "no es el snapshot oficial")

    # Strict custody: the report must exist, be complete and match exactly.
    def test_empty_report_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        silver.with_suffix(".validation.json").write_text("{}")
        self.refused(policy, silver, bronze, output, "vacío o mal formado")

    def test_malformed_report_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        for content in ("[]", '"passed"', "{not json"):
            with self.subTest(content=content):
                silver.with_suffix(".validation.json").write_text(content)
                self.refused(policy, silver, bronze, output, "validation.json")

    def test_passed_must_be_exactly_true(self):
        policy, silver, bronze, output = environment(self.folder)
        for value in ("true", 1, None):
            with self.subTest(passed=value):
                write_provenance(self.folder, policy, silver, bronze, passed=value)
                self.refused(policy, silver, bronze, output, "no fue aprobada")

    def test_report_without_sha_or_lineage_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        write_provenance(self.folder, policy, silver, bronze, sha256=None)
        self.refused(policy, silver, bronze, output, "no registra el SHA-256")
        write_provenance(self.folder, policy, silver, bronze, lineage=None)
        self.refused(policy, silver, bronze, output, "no registra el linaje")
        write_provenance(self.folder, policy, silver, bronze)
        lineage = json.loads(silver.with_suffix(".validation.json").read_text())["lineage"]
        incomplete = {k: v for k, v in lineage.items() if k != "code_sha256"}
        write_provenance(self.folder, policy, silver, bronze, lineage=incomplete)
        self.refused(policy, silver, bronze, output, "linaje de Silver incompleto")

    def test_wrong_bronze_size_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        manifest = Path(policy["inputs"]["bronze"]["manifest"])
        manifest.write_text(json.dumps({"sha256": sha(bronze), "size_bytes": bronze.stat().st_size + 1}))
        self.refused(policy, silver, bronze, output, "no es el snapshot oficial")

    def test_outdated_recipe_field_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        lineage = json.loads(silver.with_suffix(".validation.json").read_text())["lineage"]
        write_provenance(self.folder, policy, silver, bronze,
                         lineage={**lineage, "code_sha256": {**lineage["code_sha256"], "build_silver.py": "2" * 64}})
        self.refused(policy, silver, bronze, output, "desactualizada")
        write_provenance(self.folder, policy, silver, bronze, policy={"version": 0})
        self.refused(policy, silver, bronze, output, "desactualizada")

    def test_truncated_silver_is_refused(self):
        policy, silver, bronze, output = environment(self.folder)
        data = silver.read_bytes()
        silver.write_bytes(data[:-4096])
        self.refused(policy, silver, bronze, output, "modificado")

    def test_pending_wal_is_refused_before_reading(self):
        policy, silver, bronze, output = environment(self.folder)
        for path in (silver, bronze):
            with self.subTest(path=path.name):
                wal = path.with_name(path.name + "-wal")
                wal.write_bytes(b"\0" * 32)
                try:
                    self.refused(policy, silver, bronze, output, "cambios pendientes en WAL")
                finally:
                    wal.unlink()
        silver.with_name(silver.name + "-wal").write_bytes(b"")        # empty WAL: a clean snapshot
        build_gold.build(policy=policy, gate=fake_gate, silver_path=silver, bronze_path=bronze, output=output)

    def test_existing_valid_report_is_accepted(self):
        import gold_common
        policy, silver, bronze, output = environment(self.folder)
        custody = gold_common.silver_provenance(silver, bronze, Path(policy["inputs"]["bronze"]["manifest"]))
        self.assertEqual(custody["problems"], [])
        self.assertTrue(custody["passed"])
        self.assertEqual(custody["silver_sha256"], sha(silver))

    def test_silver_gate_must_approve_exact_snapshot(self):
        policy, silver, bronze, output = environment(self.folder)
        gate = lambda s, b, o: {**fake_gate(s, b, o), "silver_sha256": "f" * 64}
        with self.assertRaises(build_gold.GoldBuildError):
            build_gold.build(policy=policy, gate=gate, silver_path=silver, bronze_path=bronze, output=output)

    def test_failed_validation_publishes_nothing(self):
        policy, silver, bronze, output = environment(self.folder)
        failing = lambda *a: [{"check": "forced", "passed": False, "detail": "test"}]
        with self.assertRaises(build_gold.GoldBuildError):
            build_gold.build(policy=policy, gate=fake_gate, silver_path=silver, bronze_path=bronze, output=output, validate=failing)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + ".building").exists())

    def test_published_output_is_never_replaced(self):
        manifest, policy, silver, bronze, output = build_fixture(self.folder)
        before = sha(output), sha(output.with_name(output.stem + ".manifest.json"))
        with self.assertRaises(build_gold.GoldBuildError) as raised:
            build_gold.build(policy=policy, gate=fake_gate, silver_path=silver, bronze_path=bronze, output=output)
        self.assertIn("Se conserva", str(raised.exception))
        self.assertEqual((sha(output), sha(output.with_name(output.stem + ".manifest.json"))), before)

    def test_silver_changed_during_read_aborts(self):
        manifest, policy, silver, bronze, output = build_fixture(self.folder)
        def tamper(*args):
            with closing(sqlite3.connect(silver)) as conn:
                conn.execute("INSERT INTO silver_run VALUES ('late', '{}')")
                conn.commit()
            return [{"check": "ok", "passed": True}]
        with self.assertRaises(build_gold.GoldBuildError):
            build_gold.build(policy=policy, gate=fake_gate, silver_path=silver, bronze_path=bronze, output=output, validate=tamper)

    def test_rebuild_goes_to_a_new_version(self):
        manifest, policy, silver, bronze, output = build_fixture(self.folder)
        before = sha(output)
        other = self.folder / "gold-2" / "ufo_gold.db"
        second = build_gold.build(policy=policy, gate=fake_gate, silver_path=silver, bronze_path=bronze, output=other)
        self.assertEqual(second["load_id"], manifest["load_id"])      # same inputs and definitions → same load
        self.assertEqual(sha(output), before)                          # the first version is untouched

    def test_unlabelled_value_stops_build(self):
        from gold_fixture import reports
        rows = reports()
        rows[0]["standardized_shape"] = "Tetrahedron"
        with self.assertRaises(build_gold.GoldBuildError):
            build_fixture(self.folder, rows)


class GoldQueryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.analytics, cls.manifest, cls.paths = serving_fixture(cls.folder)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def q(self, **kw):
        return self.analytics.query(kw)

    def code(self, **kw):
        with self.assertRaises(QueryError) as ctx:
            self.analytics.query(kw)
        return ctx.exception.code

    # Contract and injection.
    def test_unknown_fields_and_sql_are_rejected(self):
        self.assertEqual(self.code(dataset="fact_report", metrics=["report_count"], sql="SELECT 1"), "contract")
        self.assertEqual(self.code(dataset="fact_report", metrics=["report_count"], filters=[{"column": "source_code", "value": "UPDB", "raw": "1=1"}]), "contract")
        self.assertEqual(self.code(dataset="fact_report", metrics=["report_count"], limit=True), "limit")
        self.assertEqual(self.code(dataset="fact_report", metrics=["report_count"], limit=501), "limit")
        self.assertEqual(self.code(dataset="fact_report", metrics=["report_count"], filters=[{"column": "event_year", "op": "gte", "value": float("nan")}], eligibility=["calendar"]), "contract")

    def test_identifiers_are_validated_and_values_bound(self):
        self.assertEqual(self.code(dataset="fact_report", group_by=['source_code"; DROP TABLE fact_report; --'], metrics=["report_count"]), "column_unknown")
        self.assertEqual(self.code(dataset="sqlite_master", metrics=["report_count"]), "dataset_unknown")
        self.assertEqual(self.code(dataset="fact_report", metrics=["report_count"], filters=[{"column": "source_code", "value": "x' OR '1'='1"}]), "value")
        result = self.q(dataset="fact_report", metrics=["report_count"], filters=[{"column": "source_record_id", "op": "eq", "value": "r1' OR '1'='1"}])
        self.assertEqual(result["rows"][0]["report_count"], 0)       # bound as a literal value
        with closing(sqlite3.connect(self.paths[3])) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM fact_report").fetchone()[0], 12)

    # Forbidden combinations.
    def test_day_requires_eligibility(self):
        self.assertEqual(self.code(dataset="fact_report", group_by=["event_date"], metrics=["report_count"]), "eligibility_missing")
        self.assertEqual(self.code(dataset="fact_report", group_by=["weekday"], metrics=["report_count"], eligibility=["calendar"]), "eligibility_missing")
        ok = self.q(dataset="fact_report", group_by=["weekday"], metrics=["report_count"], eligibility=["day"])
        self.assertEqual(sum(r["report_count"] for r in ok["rows"]), 5)      # 1, 2, 6, 10, 11

    def test_percentages_are_not_summed(self):
        self.assertEqual(self.code(dataset="agg_source", metrics=["sum_external_evidence_pct"]), "ratio_not_summable")

    def test_other_forbidden_combinations(self):
        self.assertEqual(self.code(dataset="agg_spatial_cell", group_by=["cell_lat", "cell_lng"], metrics=["report_count"]), "partition_required")
        self.assertEqual(self.code(dataset="agg_coverage", metrics=["report_count"]), "partition_required")
        self.assertEqual(self.code(dataset="fact_report", metrics=["event_count"]), "metric_unavailable")
        self.assertEqual(self.code(dataset="fact_report", view="points", limit=10), "eligibility_missing")
        self.assertEqual(self.code(dataset="agg_year", view="points"), "view_incompatible")
        self.assertEqual(self.code(dataset="fact_report", filters=[{"column": "country_iso2", "op": "is_null"}], metrics=["report_count"]), "gated_null_filter")
        self.assertEqual(self.code(dataset="agg_year", group_by=["event_year"], metrics=["report_count"], eligibility=["map"]), "eligibility_unavailable")
        self.assertEqual(self.code(dataset="agg_country", group_by=["source_code"], metrics=["report_count"], view="choropleth"), "view_contract")
        self.assertEqual(self.code(dataset="fact_report", group_by=["source_code"]), "metrics_required")
        self.assertEqual(self.code(dataset="fact_report", metrics=["real_ufo_count"]), "metric_unknown")

    def test_implied_eligibility(self):
        result = self.q(dataset="agg_month", filters=[{"column": "event_year", "op": "eq", "value": 1997}], group_by=["year_month"], metrics=["report_count"])
        self.assertEqual(result["rows"][0]["report_count"], 3)

    # Ratios, bounds and eligibility accounting.
    def test_ratios_are_recomputed(self):
        result = self.q(dataset="agg_source", group_by=["source_code"], metrics=["external_evidence_pct"], rollup=True)
        by = {r["source_code"]: r["external_evidence_pct"] for r in result["rows"]}
        self.assertEqual(by["UFO-search"], 100.0)
        self.assertEqual(result["total"]["external_evidence_pct"], round(100 * 2 / 12, 4))
        self.assertNotEqual(result["total"]["external_evidence_pct"], sum(by.values()))

    def test_report_count_is_a_single_figure(self):
        result = self.q(dataset="agg_source", group_by=["source_code"], metrics=["report_count"])
        self.assertNotIn("duplicate_bounds", result)
        for row in result["rows"]:
            self.assertNotIn("report_count_excl_candidates", row)
        # The quality columns stay in Gold and keep adding up when requested explicitly.
        both = self.q(dataset="fact_report", metrics=["report_count", "report_count_excl_candidates", "pending_candidate_reports"])["rows"][0]
        self.assertEqual(both["report_count"] - both["report_count_excl_candidates"], both["pending_candidate_reports"])

    def test_exclusions_add_up(self):
        result = self.q(dataset="fact_report", group_by=["event_hour"], metrics=["report_count"], eligibility=["hour"])
        ex = result["exclusions"]
        self.assertEqual(ex["eligible_reports"] + ex["excluded_reports"], ex["base_reports"])
        self.assertEqual(sum(r["reports"] for r in ex["excluded_by_reason"]), ex["excluded_reports"])
        self.assertIn("date_qualified", {r["reason"] for r in ex["excluded_by_reason"]})
        agg = self.q(dataset="agg_year", group_by=["event_year"], metrics=["report_count"])["exclusions"]
        self.assertEqual(agg["eligible_reports"] + agg["excluded_reports"], 12)

    # Truncation, empty results and budget.
    def test_truncation(self):
        result = self.q(dataset="fact_report", group_by=["source_code"], metrics=["report_count"], limit=1)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["matched_source_rows"], 12)

    def test_empty_result(self):
        result = self.q(dataset="fact_report", group_by=["source_code"], metrics=["report_count"],
                        filters=[{"column": "event_year", "op": "eq", "value": 1500}], eligibility=["calendar"])
        self.assertTrue(result["empty"])
        self.assertEqual(result["rows"], [])
        self.assertFalse(result["truncated"])

    def test_instruction_budget(self):
        tight = gold_query.Analytics(serving=self.analytics.path, certified_path=self.analytics.certified_path, instruction_budget=1, progress_step=1)
        with self.assertRaises(QueryError) as ctx:
            tight.query({"dataset": "fact_report", "group_by": ["source_code"], "metrics": ["report_count"]})
        self.assertEqual(ctx.exception.code, "budget")

    # Result envelope.
    def test_result_carries_provenance_query_and_limitations(self):
        result = self.q(dataset="fact_report", group_by=["country_iso2"], metrics=["report_count"], eligibility=["country"])
        prov = result["provenance"]
        self.assertEqual(prov["gold_load_id"], self.manifest["load_id"])
        self.assertEqual(prov["silver_sha256"], self.manifest["silver"]["sha256"])
        self.assertEqual(len(prov["query_sha256"]), 64)
        self.assertIn("País", result["readable_query"]["texto"])
        codes = {l["code"] for l in result["limitations"]}
        self.assertTrue({"reports_not_facts", "eligibility_country", "external_evidence"} <= codes)
        self.assertEqual(result["result_type"], "composed")
        self.assertIn("country_iso2_label", result["rows"][0])

    # Certification.
    def test_certified_query_and_loss_of_certification(self):
        certified = self.analytics.run_certified("CQ_TEST_SOURCES")
        self.assertEqual(certified["result_type"], "certified")
        self.assertEqual(self.analytics.search_certified("¿cuántos informes tiene cada fuente?")[0]["id"], "CQ_TEST_SOURCES")
        changed = self.q(dataset="agg_source", group_by=["source_code"], metrics=["report_count"], view="table")
        self.assertEqual(changed["result_type"], "composed")
        data = json.loads(self.analytics.certified_path.read_text())
        item = data["queries"][0]
        item["query"]["limit"] = 5                                      # query edited after certification
        self.assertIn("la consulta cambió desde su certificación", self.analytics.certification_status(item)["reasons"])
        item = json.loads(self.analytics.certified_path.read_text())["queries"][0]
        item["verification"]["load_id"] = "otra-carga"                  # Gold load changed
        self.assertFalse(self.analytics.certification_status(item)["valid"])

    def test_entities_and_clarification(self):
        self.assertEqual(sorted(e["id"] for e in self.analytics.find_entities("Congo")), ["CD", "CG"])
        self.assertEqual(self.analytics.find_entities("Narnia"), [])
        self.assertEqual(self.analytics.find_entities("EE. UU.")[0]["id"], "US")

    def test_serving_cache_is_verified(self):
        manifest = self.analytics.path.with_name(self.analytics.path.stem + ".manifest.json")
        original = manifest.read_text()
        try:
            manifest.write_text(json.dumps({**json.loads(original), "sha256": "0" * 64}))
            with self.assertRaises(gold_query.GoldUnavailable):
                gold_query.Analytics(serving=self.analytics.path, certified_path=self.analytics.certified_path)
        finally:
            manifest.write_text(original)


class GoldSemanticFilesTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_corrections_log_structure(self):
        log = json.loads((self.ROOT / "config/gold/corrections.json").read_text())
        self.assertEqual(set(log), {"description", "fields", "causes", "corrections"})
        evals = {q["id"] for q in json.loads((self.ROOT / "docs/GOLD_EVALS.json").read_text())["questions"]}
        for item in log["corrections"]:
            self.assertTrue(set(log["fields"]) <= set(item))
            self.assertIn(item["cause"], log["causes"])
            self.assertIn(item["eval_id"], evals)

    def test_evaluation_set_shape(self):
        evals = json.loads((self.ROOT / "docs/GOLD_EVALS.json").read_text())["questions"]
        self.assertGreaterEqual(len(evals), 50)
        categories = {q["category"] for q in evals}
        self.assertTrue({"frequent", "uncommon", "trap"} <= categories)
        certified = {q["id"] for q in json.loads((self.ROOT / "config/gold/certified_queries.json").read_text())["queries"]}
        for q in evals:
            self.assertIn(q["expected_behavior"], ("answer", "reject", "clarify"))
            if q["category"] == "frequent":
                self.assertIn(q["certified_query_id"], certified)
            if q["expected_behavior"] == "answer":
                self.assertTrue(q["expected_query"] and q["expected_view"] and q["required_limitations"])
            if q["expected_behavior"] == "reject":
                self.assertTrue(q["attempted_query"] and q["expected_error"])

    def test_certified_queries_parse_in_contract(self):
        limits = json.loads((self.ROOT / "config/gold/gold.json").read_text())["query"]
        for item in json.loads((self.ROOT / "config/gold/certified_queries.json").read_text())["queries"]:
            with self.subTest(item["id"]):
                self.assertTrue(item["title"] and item["description"] and 2 <= len(item["examples"]) <= 3 and item["limitation"])
                gold_query.Query.parse(item["query"], limits)


if __name__ == "__main__":
    unittest.main()
