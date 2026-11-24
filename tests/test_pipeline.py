"""Versioned publication, crash safety and run-context reuse (synthetic data only)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_fixture import (CERTIFIED, FakeAcceptance, changed_rows, pipeline_env, promote_silver, quiet,  # noqa: E402
                              run_gold)
from gold_fixture import sha, write_provenance  # noqa: E402

import build_all  # noqa: E402
import gold_query  # noqa: E402
import pipeline_context  # noqa: E402
import releases  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).resolve().parent / "pipeline_fixture.py"
VERSIONED = [ROOT / "config/gold/certified_queries.json", ROOT / "docs/GOLD_EVALS.json", ROOT / "docs/GOLD_CATALOG.json",
             ROOT / "docs/GOLD_CATALOG.md", ROOT / "docs/GOLD_ENTITIES.json"]


def fingerprint(paths):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}


def worker(folder, mode, **kw):
    return subprocess.Popen([sys.executable, str(WORKER), str(folder), mode], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.env = pipeline_env(self.folder)
        self.data = self.env["data"]

    def tearDown(self):
        self.tmp.cleanup()

    def approved_gold(self):
        return releases.approved(self.data, "gold")

    def assert_complete(self, item):
        """The approved version is one complete, unmixed set of files."""
        layout = releases.GoldLayout(item["path"])
        release = releases.check_release(layout.directory, item["release_sha256"])
        for name in ("ufo_gold.db", "serving/ufo_gold_serving.db", "certified_queries.json", "GOLD_EVALS.json",
                     "ufo_gold.verification.json", "ufo_gold.readiness.json", f"evals/{item['identity']}.json"):
            self.assertIn(name, release["files"])
        for path in (layout.manifest, layout.serving_manifest, layout.verification, layout.readiness, layout.evals_spec):
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("load_id", (doc.get("reference_load") or {}).get("load_id")), item["identity"], path.name)
        return layout

    # --solo gold -----------------------------------------------------------
    def test_solo_gold_with_valid_silver_promotes_one_complete_load(self):
        before = fingerprint(VERSIONED + [self.env["certified"], self.env["evals"]])
        acceptance = FakeAcceptance()
        self.assertEqual(run_gold(self.env, acceptance), 0)
        item = self.approved_gold()
        self.assertEqual(item["parent_version"], self.env["silver_version"])
        layout = self.assert_complete(item)
        self.assertTrue(json.loads(layout.readiness.read_text())["ready_for_agent"])
        # The versioned references of the checkout (and the sources) are not rewritten.
        self.assertEqual(fingerprint(VERSIONED + [self.env["certified"], self.env["evals"]]), before)
        # Silver acceptance ran once although the model gate, the evaluation and ready_for_agent all need it.
        self.assertEqual(len(acceptance.calls), 1)
        metrics = json.loads((self.data / "build.metrics.json").read_text())["metrics"]
        self.assertEqual(metrics["silver_acceptance_runs"], 1)
        self.assertEqual(metrics["hash_reads"]["repeated_files"], {})
        read = {Path(r["path"]).name for r in metrics["hash_reads"]["reads"]}
        self.assertTrue({"ufo.db", "ufo_gold.db", "ufo_gold_serving.db"} <= read)
        self.assertEqual([p["status"] for p in metrics["phases"]], ["ok"] * len(metrics["phases"]))

    def test_new_invocation_verifies_again(self):
        self.assertEqual(run_gold(self.env), 0)
        first = pipeline_context.current()
        acceptance = FakeAcceptance()
        self.assertEqual(run_gold(self.env, acceptance), 0)
        self.assertIsNot(pipeline_context.current(), first)
        self.assertEqual(len(acceptance.calls), 1)          # accepted again in the new process context
        silver = releases.SilverLayout(releases.approved(self.data, "silver")["path"]).database
        reads = [r["path"] for r in pipeline_context.current().hash_reads]
        self.assertIn(str(silver.resolve()), reads)          # and hashed again

    def test_solo_gold_with_tampered_silver_is_refused(self):
        self.assertEqual(run_gold(self.env), 0)
        previous = self.approved_gold()
        silver = releases.SilverLayout(releases.approved(self.data, "silver")["path"]).database
        with open(silver, "r+b") as stream:
            stream.seek(200)
            stream.write(b"tampered")
        acceptance = FakeAcceptance()
        self.assertEqual(run_gold(self.env, acceptance), build_all.EXIT_FAILED)
        self.assertEqual(self.approved_gold()["version"], previous["version"])
        self.assertEqual(acceptance.calls, [])                # refused before the acceptance and the build
        metrics = json.loads((self.data / "build.metrics.json").read_text())
        self.assertEqual(metrics["failed_phase"], "gold")
        self.assertIn("no coincide con su publicación", metrics["error"])

    def test_solo_gold_with_outdated_silver_report_is_refused(self):
        silver = releases.SilverLayout(releases.approved(self.data, "silver")["path"])
        lineage = json.loads(silver.validation.read_text())["lineage"]
        promote_silver(self.env, lineage={**lineage, "run_id": "1" * 64})
        self.assertEqual(run_gold(self.env), build_all.EXIT_FAILED)
        self.assertIsNone(self.approved_gold())
        error = json.loads((self.data / "build.metrics.json").read_text())["error"]
        self.assertIn("desactualizada", error)

    def test_solo_gold_with_empty_silver_report_is_refused(self):
        directory = releases.new_candidate(self.data, "silver", owner="pipeline")
        layout = releases.SilverLayout(directory)
        import gold_fixture
        gold_fixture.write_silver(layout.database)
        layout.validation.write_text("{}")
        releases.write_release(directory, "silver", sha(layout.database))
        releases.promote(self.data, "silver", directory, sha(layout.database))
        self.assertEqual(run_gold(self.env), build_all.EXIT_FAILED)
        self.assertIn("vacío o mal formado", json.loads((self.data / "build.metrics.json").read_text())["error"])

    def test_without_approved_silver_gold_is_not_attempted(self):
        empty = self.folder / "empty"
        code = build_all.run(["--solo", "gold", "--datos", str(empty)], bronze_manifest=self.env["manifest"],
                             acceptance=FakeAcceptance(), out=quiet)
        self.assertEqual(code, build_all.EXIT_FAILED)
        self.assertIn("No hay una Silver aprobada", json.loads((empty / "build.metrics.json").read_text())["error"])

    # Failures and interruptions -------------------------------------------
    def test_failure_just_before_promotion_keeps_previous_load(self):
        self.assertEqual(run_gold(self.env), 0)
        previous = self.approved_gold()
        promote_silver(self.env, changed_rows())

        def interrupt(layer, candidate):
            self.assertTrue(releases.check_release(candidate.directory)["files"])     # fully built and verified
            raise KeyboardInterrupt
        self.assertEqual(run_gold(self.env, before_promote=interrupt), 130)
        self.assertEqual(self.approved_gold()["version"], previous["version"])

        def crash(layer, candidate):
            raise OSError("disco desconectado")
        with self.assertRaises(OSError):
            run_gold(self.env, before_promote=crash)
        self.assertEqual(self.approved_gold()["version"], previous["version"])
        self.assert_complete(self.approved_gold())
        analytics = gold_query.Analytics(data=self.data)
        self.assertEqual(analytics.load_id, previous["identity"])
        self.assertEqual(analytics.coherence_problems(), [])
        # The next good build promotes the new load and removes the orphan candidates.
        self.assertEqual(run_gold(self.env), 0)
        current = self.approved_gold()
        self.assertNotEqual(current["identity"], previous["identity"])
        gold_dirs = {p.name for p in (self.data / "gold" / "versions").iterdir()}
        self.assertEqual(gold_dirs, {previous["version"], current["version"]})

    def test_killed_process_before_promotion_keeps_previous_load_and_releases_lock(self):
        self.assertEqual(run_gold(self.env), 0)
        previous = self.approved_gold()
        promote_silver(self.env, changed_rows())
        proc = worker(self.folder, "gold-stall")
        try:
            line = proc.stdout.readline()
            while line and not line.startswith("ready"):
                line = proc.stdout.readline()
            self.assertTrue(line.startswith("ready"), proc.stderr.read() if not line else line)
            self.assertEqual(run_gold(self.env), build_all.EXIT_LOCKED)          # publication in progress
            proc.kill()
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.stdout.close(); proc.stderr.close(); proc.stdin.close()
        self.assertEqual(self.approved_gold()["version"], previous["version"])
        self.assertEqual(gold_query.Analytics(data=self.data).load_id, previous["identity"])
        self.assertEqual(run_gold(self.env), 0)                                    # the OS released the lock

    # Concurrency ----------------------------------------------------------
    def test_lock_is_exclusive_across_processes(self):
        proc = worker(self.folder, "hold-lock")
        try:
            self.assertEqual(proc.stdout.readline().strip(), "locked")
            self.assertEqual(run_gold(self.env), build_all.EXIT_LOCKED)
            self.assertFalse((self.data / "gold" / "versions").exists())          # nothing was even started
            with self.assertRaises(releases.BuildLocked):
                with releases.build_lock(self.data):
                    pass
        finally:
            proc.stdin.close()
            proc.wait(timeout=30)
            proc.stdout.close(); proc.stderr.close()
        self.assertEqual(run_gold(self.env), 0)

    def test_simultaneous_builds_never_mix_files(self):
        procs = [worker(self.folder, "gold") for _ in range(3)]
        codes = []
        for proc in procs:
            proc.wait(timeout=120)
            codes.append(proc.returncode)
            proc.stdin.close(); proc.stdout.close(); proc.stderr.close()
        self.assertTrue(set(codes) <= {0, build_all.EXIT_LOCKED}, codes)
        self.assertIn(0, codes)
        item = self.approved_gold()
        self.assert_complete(item)
        promoted = [v for v in releases.versions(self.data, "gold") if v["promoted_at"]]
        self.assertEqual(len(promoted), codes.count(0))
        for version in promoted:
            directory = self.data / Path(*version["directory"].split("/"))
            if directory.exists():
                release = releases.check_release(directory)
                self.assertEqual(release["version"], version["version"])

    def test_candidate_names_are_unique(self):
        names = {releases.new_candidate(self.data, "gold").name for _ in range(50)}
        self.assertEqual(len(names), 50)

    # Versioned references -------------------------------------------------
    def test_references_change_only_with_the_explicit_operation(self):
        self.assertEqual(run_gold(self.env), 0)
        root = self.folder / "repo"
        (root / "config/gold").mkdir(parents=True)
        (root / "docs").mkdir()
        (root / "config/gold/certified_queries.json").write_text(json.dumps(CERTIFIED), encoding="utf-8")
        (root / "docs/GOLD_EVALS.json").write_text(self.env["evals"].read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(build_all.update_references(self.data, root, out=quiet), 0)
        layout = releases.GoldLayout(self.approved_gold()["path"])
        self.assertEqual((root / "docs/GOLD_EVALS.json").read_bytes(), layout.evals_spec.read_bytes())
        self.assertEqual(json.loads((root / "config/gold/certified_queries.json").read_text())["queries"][0]["verification"]["load_id"],
                         self.approved_gold()["identity"])
        self.assertTrue((root / "docs/GOLD_CATALOG.md").exists())
        self.assertNotIn(b"\r\n", (root / "docs/GOLD_EVALS.json").read_bytes())
        # Definitions edited after the load: the references are kept.
        edited = json.loads((root / "config/gold/certified_queries.json").read_text())
        edited["queries"][0]["title"] = "Otro título"
        (root / "config/gold/certified_queries.json").write_text(json.dumps(edited), encoding="utf-8")
        self.assertEqual(build_all.update_references(self.data, root, out=quiet), build_all.EXIT_FAILED)
        self.assertEqual(json.loads((root / "config/gold/certified_queries.json").read_text())["queries"][0]["title"], "Otro título")


class SilverPhaseTest(unittest.TestCase):
    """The Silver/report pair is promoted only after custody, acceptance and review."""

    def setUp(self):
        from unittest.mock import patch
        import gold_fixture
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.env = pipeline_env(self.folder)
        self.data = self.env["data"]
        self.first = releases.approved(self.data, "silver")
        env = self.env

        def fake_build(source, target, manifest, policy, replace=False):
            # Same publication as the real build: a complete database, then its report.
            gold_fixture.write_silver(target, changed_rows())
            write_provenance(env["folder"], None, target, source, manifest=env["manifest"])
            return {"passed": True}
        self.review = {"candidate_pairs_classified": 0}

        def fake_review(*args):
            if self.review is None:
                raise ValueError("revisión rota")
            return self.review
        patches = [patch("build_silver.build", fake_build), patch("review_silver.review", fake_review)]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def run_silver(self, **kw):
        return build_all.run(["--solo", "silver", "--datos", str(self.data)], bronze_manifest=self.env["manifest"],
                             acceptance=kw.pop("acceptance", FakeAcceptance()), out=quiet, **kw)

    def test_silver_pair_is_promoted_after_its_controls(self):
        acceptance = FakeAcceptance()
        self.assertEqual(self.run_silver(acceptance=acceptance), 0)
        current = releases.approved(self.data, "silver")
        self.assertNotEqual(current["version"], self.first["version"])
        layout = releases.SilverLayout(current["path"])
        release = releases.check_release(layout.directory, current["release_sha256"])
        self.assertEqual(set(release["files"]), {"ufo.db", "ufo.validation.json", "ufo.readiness.json", "ufo.review.json"})
        self.assertEqual(current["identity"], sha(layout.database))
        self.assertEqual(len(acceptance.calls), 1)

    def test_failed_review_keeps_previous_silver(self):
        self.review = None
        self.assertEqual(self.run_silver(), build_all.EXIT_FAILED)
        self.assertEqual(releases.approved(self.data, "silver")["version"], self.first["version"])

    def test_interrupted_before_promotion_keeps_previous_silver(self):
        def interrupt(layer, candidate):
            raise KeyboardInterrupt
        self.assertEqual(self.run_silver(before_promote=interrupt), 130)
        self.assertEqual(releases.approved(self.data, "silver")["version"], self.first["version"])

    def test_silver_then_gold_in_one_run_accepts_once(self):
        acceptance = FakeAcceptance()
        code = build_all.run(["--desde", "silver", "--datos", str(self.data)], bronze_manifest=self.env["manifest"],
                             certified_source=self.env["certified"], evals_source=self.env["evals"],
                             acceptance=acceptance, out=quiet)
        self.assertEqual(code, 0)
        silver, gold = releases.approved(self.data, "silver"), releases.approved(self.data, "gold")
        self.assertEqual(gold["parent_version"], silver["version"])
        self.assertEqual(len(acceptance.calls), 1)           # Silver promotion and every Gold step share it
        reads = json.loads((self.data / "build.metrics.json").read_text())["metrics"]["hash_reads"]
        self.assertEqual(reads["repeated_files"], {})


class ContextTest(unittest.TestCase):
    def test_digest_reads_a_stable_file_once_and_rereads_after_a_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.bin"
            path.write_bytes(b"a" * 1000)
            ctx = pipeline_context.RunContext()
            first = ctx.digest(path)
            self.assertEqual(ctx.digest(path), first)
            self.assertEqual(len(ctx.hash_reads), 1)
            path.write_bytes(b"b" * 1001)
            self.assertNotEqual(ctx.digest(path), first)
            self.assertEqual(len(ctx.hash_reads), 2)

    def test_rename_keeps_the_hash_without_reading_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "part", Path(tmp) / "final"
            source.write_bytes(b"c" * 1000)
            ctx = pipeline_context.RunContext()
            value = ctx.digest(source)
            ctx.replace(source, target)
            self.assertEqual(ctx.digest(target), value)
            self.assertEqual(len(ctx.hash_reads), 1)

    def test_acceptance_once_per_exact_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            silver, bronze = Path(tmp) / "s.db", Path(tmp) / "b.db"
            silver.write_bytes(b"s"); bronze.write_bytes(b"b")
            ctx = pipeline_context.RunContext()
            calls = []
            compute = lambda s, b: calls.append(1) or {"ready_for_gold": True}
            ctx.silver_acceptance(silver, bronze, compute)
            ctx.silver_acceptance(silver, bronze, compute)
            self.assertEqual(len(calls), 1)
            silver.write_bytes(b"s2")
            ctx.silver_acceptance(silver, bronze, compute)
            self.assertEqual(len(calls), 2)

    def test_text_fingerprints_ignore_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            lf, crlf = Path(tmp) / "lf.py", Path(tmp) / "crlf.py"
            lf.write_bytes(b"a = 1\nb = 2\n")
            crlf.write_bytes(b"a = 1\r\nb = 2\r\n")
            self.assertEqual(pipeline_context.text_digest_file(lf), pipeline_context.text_digest_file(crlf))
            out = Path(tmp) / "out.json"
            pipeline_context.write_text(out, "x\ny\n")
            self.assertEqual(out.read_bytes(), b"x\ny\n")


if __name__ == "__main__":
    unittest.main()
