"""Exercise ingestion failures without downloading the production database."""
import copy
from contextlib import closing
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_bronze.py"
SPEC = importlib.util.spec_from_file_location("bronze", SCRIPT)
bronze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bronze)


class BronzeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "official.db"
        with closing(sqlite3.connect(self.source)) as db, db:
            db.executescript("""
                CREATE TABLE source_database (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE source_origin (id INTEGER PRIMARY KEY);
                CREATE TABLE location (id INTEGER PRIMARY KEY);
                CREATE TABLE sighting (
                    id INTEGER PRIMARY KEY, source_db_id INTEGER, location_id INTEGER,
                    origin_id INTEGER, date_event TEXT, lat REAL, lng REAL,
                    quality_score INTEGER, source_record_id TEXT
                );
                CREATE TABLE sighting_analysis (id INTEGER PRIMARY KEY, sighting_id INTEGER);
                CREATE TABLE duplicate_candidate (
                    id INTEGER PRIMARY KEY, sighting_id_a INTEGER, sighting_id_b INTEGER
                );
                INSERT INTO source_database VALUES (1, 'UFOCAT');
                INSERT INTO source_origin VALUES (1);
                INSERT INTO location VALUES (1);
                INSERT INTO sighting VALUES (1, 1, 1, 1, '2020-01-01', 10, -84, 60, 'abc');
                INSERT INTO sighting_analysis VALUES (1, 1);
                INSERT INTO duplicate_candidate VALUES (1, 1, 1);
            """)
        self.manifest = {
            "release": "test", "release_url": "https://example.invalid/release",
            "asset_url": self.source.as_uri(),
            "expected_sources": {"UFOCAT": 1},
            "expected_metrics": {"total": 1, "coords": 1, "duplicate_candidates": 1},
        }
        self.refresh_asset()
        self.target = self.root / "bronze/ufo.db"

    def refresh_asset(self):
        self.manifest.update(size_bytes=self.source.stat().st_size,
                             sha256=hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_valid_snapshot_is_preserved_byte_for_byte(self):
        before = self.source.read_bytes()
        report = bronze.validate(self.source, self.manifest)
        self.assertTrue(report["passed"])
        self.assertEqual(report["layer"], "bronze")
        self.assertEqual(before, self.source.read_bytes())

    def test_checksum_mismatch_is_rejected_before_opening_sqlite(self):
        self.source.write_bytes(b"invalid database")
        report = bronze.validate(self.source, self.manifest)
        self.assertFalse(report["passed"])
        self.assertEqual(list(report["checks"]), ["asset"])

    def test_unexpected_count_fails(self):
        self.manifest["expected_metrics"]["total"] = 2
        self.assertFalse(bronze.validate(self.source, self.manifest)["passed"])

    def test_unexpected_source_fails(self):
        self.manifest["expected_sources"] = {"OTHER": 1}
        self.assertFalse(bronze.validate(self.source, self.manifest)["passed"])

    def test_orphan_is_rejected_without_foreign_key_declarations(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE sighting SET location_id=999")
        self.refresh_asset()
        report = bronze.validate(self.source, self.manifest)
        self.assertFalse(report["passed"])
        self.assertEqual(report["checks"]["orphans_sighting_location_id"]["actual"], 1)

    def test_private_narrative_column_is_rejected(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("ALTER TABLE sighting ADD COLUMN description TEXT")
        self.refresh_asset()
        report = bronze.validate(self.source, self.manifest)
        self.assertFalse(report["passed"])
        self.assertEqual(report["checks"]["public_export"]["raw_columns_present"], ["description"])

    @unittest.skipUnless(shutil.which("curl"), "curl is required for download")
    def test_download_and_rerun_without_network(self):
        bronze.download(self.target, self.manifest)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        with patch.object(bronze.subprocess, "run", side_effect=AssertionError("unexpected download")):
            bronze.download(self.target, self.manifest)
        self.assertFalse(self.target.with_suffix(".db.part").exists())

    def test_existing_different_database_is_never_overwritten(self):
        self.target.parent.mkdir()
        self.target.write_bytes(b"keep this")
        with self.assertRaises(RuntimeError):
            bronze.download(self.target, self.manifest)
        self.assertEqual(self.target.read_bytes(), b"keep this")

    def test_completed_partial_is_recovered_without_downloading(self):
        self.target.parent.mkdir()
        part = self.target.with_suffix(".db.part")
        shutil.copyfile(self.source, part)
        with patch.object(bronze.subprocess, "run", side_effect=AssertionError("unexpected download")):
            bronze.download(self.target, self.manifest)
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())
        self.assertFalse(part.exists())

    @unittest.skipUnless(shutil.which("curl"), "curl is required for download")
    def test_bad_download_is_not_promoted_to_bronze(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["sha256"] = "0" * 64
        with self.assertRaises(RuntimeError):
            bronze.download(self.target, manifest)
        self.assertFalse(self.target.exists())
        self.assertTrue(self.target.with_suffix(".db.part").exists())

    def test_cli_writes_report_and_fails_on_invalid_existing_database(self):
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest))
        with patch.object(bronze, "MANIFEST", manifest_path), patch(
            "sys.argv", [str(SCRIPT), "--database", str(self.source), "--verify-only"]
        ):
            self.assertEqual(bronze.main(), 0)
            report_path = self.source.with_suffix(".validation.json")
            self.assertTrue(json.loads(report_path.read_text())["passed"])
            self.source.write_bytes(b"bad")
            self.assertEqual(bronze.main(), 1)
            self.assertFalse(json.loads(report_path.read_text())["passed"])


if __name__ == "__main__":
    unittest.main()
