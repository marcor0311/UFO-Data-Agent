"""Verify Silver projection, source preservation, and loss-prevention failures."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_silver as silver


class SilverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "bronze.db"
        self.target = self.root / "silver/ufo.db"
        self.policy = {
            "version": 1,
            "drop_columns": {
                "source_database": ["record_count"],
                "sighting": ["reddit_post_id", "topic_id"],
                "duplicate_candidate": ["resolved_at"],
            },
        }
        with closing(sqlite3.connect(self.source)) as db, db:
            db.executescript("""
                CREATE TABLE source_database (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    record_count INTEGER
                );
                CREATE TABLE sighting (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_db_id INTEGER NOT NULL REFERENCES source_database(id),
                    -- Reserved fields, including an inline unique constraint.
                    reddit_post_id TEXT UNIQUE,
                    topic_id INTEGER,
                    shape TEXT DEFAULT 'round, flat',
                    note TEXT DEFAULT 'topic_id, ) -- still text',
                    score INTEGER CHECK (score BETWEEN 0 AND 100)
                );
                CREATE TABLE duplicate_candidate (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sighting_id_a INTEGER NOT NULL REFERENCES sighting(id),
                    sighting_id_b INTEGER NOT NULL REFERENCES sighting(id),
                    resolved_at TEXT,
                    status TEXT DEFAULT 'pending',
                    UNIQUE (sighting_id_a, sighting_id_b)
                );
                CREATE INDEX idx_sighting_topic ON sighting(topic_id);
                CREATE INDEX idx_sighting_reddit ON sighting(reddit_post_id);
                CREATE INDEX idx_sighting_source ON sighting(source_db_id);
                INSERT INTO source_database (id, name) VALUES (1, 'UFOCAT');
                INSERT INTO sighting (id, source_db_id, shape, note, score)
                    VALUES (10, 1, 'disc', 'texto original', 0);
                INSERT INTO duplicate_candidate (sighting_id_a, sighting_id_b)
                    VALUES (10, 10);
                UPDATE sqlite_sequence SET seq=99 WHERE name='sighting';
            """)
        self.manifest = {"dataset": "ufo", "expected_metrics": {"total": 1}, "expected_sources": {"UFOCAT": 1}}
        self.refresh_asset()

    def refresh_asset(self):
        self.manifest.update(size_bytes=self.source.stat().st_size, sha256=silver.digest(self.source))

    def build(self):
        return silver.build(self.source, self.target, self.manifest, self.policy)

    def test_projection_preserves_rows_constraints_and_bronze(self):
        before = self.source.read_bytes()
        report = self.build()
        self.assertEqual(self.source.read_bytes(), before)
        self.assertTrue(report["passed"])
        self.assertEqual(report["table_counts"], {"duplicate_candidate": 1, "sighting": 1, "source_database": 1})
        self.assertEqual(set(report["removed_indexes"]), {"idx_sighting_topic", "idx_sighting_reddit"})
        with closing(sqlite3.connect(self.target)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            self.assertEqual(db.execute("SELECT * FROM sighting").fetchone(), (10, 1, "disc", "texto original", 0))
            self.assertNotIn("resolved_at", {col[1] for col in silver.columns(db, "duplicate_candidate")})
            self.assertEqual(db.execute("SELECT seq FROM sqlite_sequence WHERE name='sighting'").fetchone()[0], 99)
            self.assertIsNotNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='idx_sighting_source'").fetchone())
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO sighting (source_db_id) VALUES (999)")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO source_database (name) VALUES ('UFOCAT')")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO duplicate_candidate (sighting_id_a,sighting_id_b) VALUES (10,10)")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO sighting (source_db_id,score) VALUES (1,101)")
            db.execute("INSERT INTO sighting (source_db_id) VALUES (1)")
            self.assertEqual(db.execute("SELECT id,shape,note FROM sighting WHERE id=100").fetchone(), (100, "round, flat", "topic_id, ) -- still text"))
        stored = json.loads(self.target.with_suffix(".validation.json").read_text())
        self.assertEqual(stored["sha256"], silver.digest(self.target))

    def test_informative_values_in_candidates_are_never_discarded(self):
        for value in (0, 1, "[]", "{}", "unknown", "null"):
            with self.subTest(value=value):
                with closing(sqlite3.connect(self.source)) as db, db:
                    db.execute("UPDATE sighting SET topic_id=?", (value,))
                self.refresh_asset()
                with self.assertRaisesRegex(ValueError, "contiene datos"):
                    self.build()
                self.assertFalse(self.target.exists())
                self.assertFalse(self.target.with_suffix(".validation.json").exists())

    def test_blank_text_is_empty(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE sighting SET reddit_post_id=?", (" \t\r\n\v\f",))
        self.refresh_asset()
        self.assertTrue(self.build()["passed"])

    def test_wrong_bronze_is_rejected_before_creating_output(self):
        self.manifest["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "manifiesto"):
            self.build()
        self.assertFalse(self.target.exists())

    def test_same_path_and_existing_output_are_preserved(self):
        with self.assertRaisesRegex(ValueError, "distinta"):
            silver.build(self.source, self.source, self.manifest, self.policy)
        self.target.parent.mkdir()
        self.target.write_bytes(b"keep this")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(self.target.read_bytes(), b"keep this")

    def test_failed_validation_does_not_publish_silver(self):
        self.manifest["expected_metrics"]["total"] = 2
        with self.assertRaisesRegex(ValueError, "verificaciones"):
            self.build()
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.iterdir()), [])

    def test_orphan_fails_validation(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE sighting SET source_db_id=999")
        self.refresh_asset()
        with self.assertRaisesRegex(ValueError, "foreign_keys"):
            self.build()
        self.assertFalse(self.target.exists())

    def test_missing_candidate_requires_policy_review(self):
        self.policy["drop_columns"]["sighting"].append("missing")
        with self.assertRaisesRegex(ValueError, "Columnas ausentes"):
            self.build()
        self.assertFalse(self.target.exists())

    def test_cli_builds_database_and_report(self):
        manifest = self.root / "bronze.json"
        policy = self.root / "silver.json"
        manifest.write_text(json.dumps(self.manifest))
        policy.write_text(json.dumps(self.policy))
        with patch.object(silver, "MANIFEST", manifest), patch.object(silver, "POLICY", policy), patch(
            "sys.argv", ["build_silver.py", "--source", str(self.source), "--database", str(self.target)]
        ):
            self.assertEqual(silver.main(), 0)
        self.assertTrue(self.target.exists())
        self.assertTrue(self.target.with_suffix(".validation.json").exists())


if __name__ == "__main__":
    unittest.main()
