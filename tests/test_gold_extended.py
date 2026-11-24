"""Expanded Gold: Silver descriptors, registers and logs, measures, quantiles and analyses (synthetic fixture)."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from gold_fixture import serving_fixture  # noqa: E402
import gold_analysis  # noqa: E402
import gold_descriptors as d  # noqa: E402
from gold_query import OTHER, POINTS_MAX_REPORTS, Query, QueryError  # noqa: E402


class DescriptorsTest(unittest.TestCase):
    def test_closed_vocabularies(self):
        self.assertEqual(d.sound_type("No sound"), "silent")
        self.assertEqual(d.sound_type("LowHum"), "humming")
        self.assertIsNone(d.sound_type("unk"))
        self.assertEqual(d.sound_type("Noise"), "other")
        self.assertEqual(d.direction_code("nne"), "N")
        self.assertEqual(d.direction_code("from SW to NE"), "SW")
        self.assertEqual(d.direction_code("left"), "other")
        self.assertEqual(d.weather_type("partly cloudy"), "partly_cloudy")
        self.assertEqual(d.terrain_type("at cruising altitude"), "airborne")
        self.assertEqual(d.vallee_code("fb1"), "FB1")
        self.assertIsNone(d.vallee_code("FB!"))

    def test_regions_only_where_the_list_is_closed(self):
        self.assertEqual(d.region_code("NM", "US"), "US-NM")
        self.assertEqual(d.region_code("New Mexico", "US"), "US-NM")
        self.assertEqual(d.region_code("SAU", "AU"), "AU-SA")
        self.assertIsNone(d.region_code("ON", "US"))       # a Canadian code in the United States
        self.assertIsNone(d.region_code("Lombardy", "IT"))  # no closed list outside US, CA, AU
        self.assertEqual(d.city_name("  albuquerque "), "Albuquerque")
        self.assertIsNone(d.city_name("unknown"))

    def test_bands(self):
        self.assertEqual([d.witness_band(n) for n in (None, 0, 1, 2, 4, 8, 40)], [None, "w0", "w1", "w2", "w3_5", "w6_10", "w11_plus"])
        self.assertEqual([d.pending_pair_band(n) for n in (0, 1, 3, 9)], ["p0", "p1", "p3_5", "p6_plus"])
        self.assertEqual(d.similarity_band(0.96), "s95")


class ExtendedGoldTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.a, cls.manifest, cls.paths = serving_fixture(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def q(self, **kw):
        return self.a.query(kw)

    def code(self, **kw):
        with self.assertRaises(QueryError) as ctx:
            self.a.query(kw)
        return ctx.exception.code

    def test_model_columns_from_silver(self):
        with sqlite3.connect(self.paths[3]) as con:
            row = con.execute("SELECT region_code, city_name, sound_type, direction_code, weather_type, terrain_type, vallee_code, "
                              "witness_band, pending_pair_band, within_10km FROM fact_report WHERE report_id=1").fetchone()
            self.assertEqual(row, ("US-NM", "Albuquerque", "silent", "NE", "clear", "rural", "CE1", "w2", "p1", 1))
            # A city is published only where the report's country is the canonical one and eligible.
            self.assertIsNone(con.execute("SELECT city_name FROM fact_report WHERE report_id=7").fetchone()[0])
            self.assertEqual(con.execute("SELECT COUNT(*) FROM report_behavior_tag").fetchone()[0], 7)
            self.assertEqual(con.execute("SELECT crew_count FROM fact_crash_retrieval").fetchone()[0], "3-4")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM facility_catalog WHERE admitted=0").fetchone()[0], 1)

    def test_points_are_complete(self):
        result = self.q(dataset="fact_report", view="points", eligibility=["map"], limit=2)   # limit no longer cuts the map
        total = self.q(dataset="fact_report", metrics=["report_count"], eligibility=["map"])["rows"][0]["report_count"]
        self.assertEqual(result["row_count"], total)
        self.assertEqual(result["points"], {"reports": total, "grouped": False, "max_reports": POINTS_MAX_REPORTS})
        self.assertFalse(result["truncated"])
        cases = self.q(dataset="fact_nuclear_encounter", view="points", eligibility=["map"])
        self.assertEqual(cases["rows"][0]["case_id"], 1)

    def test_grouped_points_keep_every_report(self):
        import gold_query
        old = gold_query.POINTS_MAX_REPORTS
        gold_query.POINTS_MAX_REPORTS = 2
        try:
            result = self.q(dataset="fact_report", view="points", eligibility=["map"])
        finally:
            gold_query.POINTS_MAX_REPORTS = old
        self.assertTrue(result["points"]["grouped"])
        self.assertEqual(sum(r["report_count"] for r in result["rows"]), result["points"]["reports"])

    def test_quantiles_and_boxes(self):
        bars = self.q(dataset="fact_report", view="bars", group_by=["source_code"], metrics=["median_duration_min", "report_count"],
                      order_by="median_duration_min")
        self.assertTrue(all(r["median_duration_min"] == 10.0 for r in bars["rows"] if r["source_code"] != "UPDB" or r["median_duration_min"]))
        box = self.q(dataset="fact_report", view="boxplot", group_by=["shape_code"], metrics=["median_duration_min"])
        light = next(r for r in box["rows"] if r["shape_code"] == "Light")
        positive = self.q(dataset="fact_report", metrics=["positive_duration_reports"], filters=[{"column": "shape_code", "op": "eq", "value": "Light"}])
        self.assertEqual(light["box"]["n"], positive["rows"][0]["positive_duration_reports"])
        self.assertEqual(light["box"]["p50"], 10.0)
        self.assertEqual(self.code(dataset="fact_report", view="boxplot", group_by=["shape_code"], metrics=["report_count"]), "view_contract")

    def test_measures(self):
        h = self.q(dataset="fact_report", view="histogram", metrics=["report_count"], measure="witnesses", group_by=["source_code"])
        self.assertEqual(h["distribution"]["facet"], "source_code")
        self.assertEqual(sum(s["with_value"] for s in h["distribution"]["series"]), 12)
        e = self.q(dataset="fact_report", view="ecdf", metrics=["report_count"], measure="nuclear_distance", eligibility=["nuclear_proximity"])
        self.assertEqual(e["distribution"]["unit"], "km")
        self.assertEqual(self.code(dataset="fact_report", view="ecdf", metrics=["report_count"], measure="nuclear_distance"), "eligibility_missing")
        self.assertEqual(self.code(dataset="fact_report", view="ecdf", metrics=["report_count"], measure="witnesses"), "view_contract")
        s = self.q(dataset="fact_report", view="scatter", metrics=["report_count"], measure="duration_witnesses")
        self.assertEqual(sum(r["report_count"] for r in s["rows"]), s["distribution"]["with_value"])
        self.assertEqual(self.code(dataset="fact_report", view="scatter", metrics=["report_count"], measure="vader_roberta"), "view_contract")
        self.assertEqual(self.code(dataset="fact_report", view="bars", group_by=["source_code"], metrics=["report_count"], measure="duration"), "view_contract")

    def test_measure_is_only_hashed_when_set(self):
        limits = self.a.limits
        self.assertNotIn("measure", Query.parse({"dataset": "fact_report"}, limits).canonical())
        self.assertEqual(Query.parse({"dataset": "fact_report", "view": "histogram", "measure": "witnesses"}, limits).canonical()["measure"], "witnesses")

    def test_stacked_folds_the_tail(self):
        rows = [{"decade": 1990, "shape_code": f"s{i}", "report_count": 20 - i} for i in range(15)]
        q = Query.parse({"dataset": "fact_report", "view": "stacked", "group_by": ["decade", "shape_code"], "metrics": ["report_count"]}, self.a.limits)
        out = self.a._collapse_categories(rows, q, ["report_count"])
        self.assertEqual(len(out), 12)
        self.assertEqual(sum(r["report_count"] for r in out), sum(r["report_count"] for r in rows))
        self.assertEqual(out[-1]["shape_code"], OTHER)

    def test_regions_cities_and_null_with_eligibility(self):
        r = self.q(dataset="fact_report", view="bars", group_by=["region_code"], metrics=["report_count"], eligibility=["country"],
                   filters=[{"column": "region_code", "op": "is_null", "value": False}])
        self.assertEqual([(x["region_code"], x["report_count"]) for x in r["rows"]], [("US-NM", 2)])
        self.assertEqual(self.code(dataset="fact_report", metrics=["report_count"], filters=[{"column": "region_code", "op": "is_null"}]),
                         "gated_null_filter")
        city = self.q(dataset="fact_report", metrics=["report_count"], eligibility=["country"], filters=[{"column": "city_name", "op": "eq", "value": "Albuquerque"}])
        self.assertEqual(city["rows"][0]["report_count"], 2)
        self.assertEqual(self.a.find_entities("New Mexico", kind="regions")[0]["id"], "US-NM")

    def test_conditional_ratios(self):
        r = self.q(dataset="fact_report", metrics=["within_10km_reports", "proximity_reports", "within_10km_pct"])["rows"][0]
        self.assertEqual(r["within_10km_pct"], round(100 * r["within_10km_reports"] / r["proximity_reports"], 4))
        r = self.q(dataset="fact_report", metrics=["core_fields_reports", "report_count", "core_fields_pct"])["rows"][0]
        self.assertEqual(r["core_fields_pct"], round(100 * r["core_fields_reports"] / r["report_count"], 4))

    def test_new_datasets(self):
        tags = self.q(dataset="report_behavior_tag", view="bars", group_by=["behavior_tag"], metrics=["report_count"])
        self.assertEqual({r["behavior_tag"]: r["report_count"] for r in tags["rows"]}, {"bright": 3, "hovering": 3, "silent": 1})
        pairs = self.q(dataset="candidate_pair", view="bars", group_by=["match_method"], metrics=["pair_count", "avg_similarity"])
        self.assertEqual(pairs["rows"][0]["pair_count"], 3)
        issues = self.q(dataset="quality_issue_summary", view="bars", group_by=["rule_id"], metrics=["issue_count"])
        self.assertEqual(sum(r["issue_count"] for r in issues["rows"]), 2)
        model = self.q(dataset="report_model_output", view="bars", group_by=["emotion_28_dominant"], metrics=["avg_nrc_fear"])
        self.assertEqual(model["rows"][0]["emotion_28_dominant"], "curiosity")

    def test_analysis_views_are_not_for_query_gold(self):
        self.assertEqual(self.code(dataset="fact_report", view="waterfall", metrics=["report_count"]), "view_contract")


class AnalysesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.a, _, _ = serving_fixture(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_analysis(self, kind, **params):
        return gold_analysis.analyze(self.a, {"analysis": kind, "params": params})

    def test_every_analysis_returns_an_envelope(self):
        cases = {"period_change": {"period": "decade", "from": 1950, "to": 1990}, "dominant_share": {}, "daily_anomalies": {"from_year": 1997, "to_year": 1997},
                 "yoy_change": {"from_year": 1997, "to_year": 1998}, "daily_distribution_by_month": {"from_year": 1997, "to_year": 1997},
                 "hour_month_deviation": {}, "rank_over_time": {"from_year": 1950, "to_year": 2001}, "concentration": {},
                 "cell_change": {"from": 1990, "to": 2000}, "first_appearance": {}, "clusters": {"min_reports": 2},
                 "facility_links": {}, "funnel": {}, "missing_combinations": {}, "compare_reports": {"report_ids": [1, 2]},
                 "kmeans_profiles": {"k": 2}, "retention": {}, "source_overlap": {}, "diversity": {}, "obs_expected": {"min_reports": 1}}
        self.assertEqual(set(cases), set(gold_analysis.ANALYSES))
        for kind, params in cases.items():
            with self.subTest(kind=kind):
                try:
                    r = self.run_analysis(kind, **params)
                except QueryError as exc:
                    self.assertEqual((kind, exc.code), ("kmeans_profiles", "value"))  # 12 reports cannot make profiles
                    continue
                self.assertEqual(r["view"], gold_analysis.ANALYSES[kind]["view"])
                self.assertEqual(r["query"]["analysis"], kind)
                self.assertEqual(r["provenance"]["gold_load_id"], self.a.load_id)
                self.assertTrue(r["readable_query"]["texto"].startswith("Análisis"))

    def test_period_change_adds_up(self):
        r = self.run_analysis("period_change", period="decade", **{"from": 1950, "to": 1990})
        self.assertEqual(sum(x["change"] for x in r["rows"]), r["analysis"]["total_change"])

    def test_compare_and_clusters(self):
        r = self.run_analysis("compare_reports", report_ids=[2, 6])
        self.assertEqual(r["analysis"]["candidate_pair"]["match_method"], "tier3_desc_fuzzy")
        self.assertIsNone(self.run_analysis("compare_reports", report_ids=[1, 2])["analysis"]["candidate_pair"])
        clusters = self.run_analysis("clusters", min_reports=2)
        self.assertEqual(clusters["rows"][0]["report_count"], 2)   # reports 1 and 2: same place and day (7 has no date)

    def test_parameters_are_typed(self):
        for raw, code in (({"analysis": "nope"}, "contract"), ({"analysis": "funnel", "params": {"x": 1}}, "contract"),
                          ({"analysis": "period_change", "params": {"from": 1990}}, "contract"),
                          ({"analysis": "diversity", "params": {"category": "lat"}}, "not_a_dimension"),
                          ({"analysis": "funnel", "params": {"filters": [{"column": "nope", "op": "eq", "value": 1}]}}, "column_unknown")):
            with self.subTest(raw=raw), self.assertRaises(QueryError) as ctx:
                gold_analysis.analyze(self.a, raw)
            self.assertEqual(ctx.exception.code, code)

    def test_area_limits_the_analysis(self):
        everywhere = self.run_analysis("funnel", by=None)
        area = [[-113, 33], [-111, 33], [-111, 34], [-113, 34]]
        inside = gold_analysis.analyze(self.a, {"analysis": "funnel", "params": {"by": None}}, area)
        self.assertLess(inside["rows"][0]["report_count"], everywhere["rows"][0]["report_count"])
        self.assertEqual(inside["query"]["area"], area)


if __name__ == "__main__":
    unittest.main()
