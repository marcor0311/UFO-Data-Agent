#!/usr/bin/env python3
"""Download and verify the unchanged public UFO dataset as Bronze."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/bronze.json"

METRICS = {
    "total": "SELECT COUNT(*) FROM sighting",
    "duplicate_candidates": "SELECT COUNT(*) FROM duplicate_candidate",
    "coords": "SELECT COUNT(*) FROM sighting WHERE lat IS NOT NULL AND lng IS NOT NULL",
    "valid_coords": "SELECT COUNT(*) FROM sighting WHERE lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180",
    "qs60": "SELECT COUNT(*) FROM sighting WHERE quality_score >= 60",
    "has_movement": "SELECT COUNT(*) FROM sighting WHERE has_movement_mentioned = 1",
    "movement_cats_non_empty": "SELECT COUNT(*) FROM sighting WHERE movement_categories IS NOT NULL AND movement_categories != '[]'",
    "std_shape": "SELECT COUNT(*) FROM sighting WHERE standardized_shape IS NOT NULL",
    "emotion_28": "SELECT COUNT(*) FROM sighting WHERE emotion_28_dominant IS NOT NULL",
    "emotion_7": "SELECT COUNT(*) FROM sighting WHERE emotion_7_dominant IS NOT NULL",
    "vader": "SELECT COUNT(*) FROM sighting WHERE vader_compound IS NOT NULL",
    "roberta": "SELECT COUNT(*) FROM sighting WHERE roberta_sentiment IS NOT NULL",
    "nrc": "SELECT COUNT(*) FROM sighting WHERE nrc_joy IS NOT NULL",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_asset(path: Path, manifest: dict) -> dict:
    size = path.stat().st_size
    sha = digest(path)
    return {
        "size_bytes": size, "expected_size_bytes": manifest["size_bytes"],
        "sha256": sha, "expected_sha256": manifest["sha256"],
        "passed": size == manifest["size_bytes"] and sha == manifest["sha256"],
    }


def download(path: Path, manifest: dict) -> None:
    if path.exists():
        if check_asset(path, manifest)["passed"]:
            print("La base existente coincide con la publicación oficial.", flush=True)
            return
        raise RuntimeError(f"Se conserva {path}: no coincide con la publicación. Use otra ruta.")
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    if not part.exists() or not check_asset(part, manifest)["passed"]:
        subprocess.run([
            "curl", "--fail", "--location", "--retry", "3", "--continue-at", "-",
            "--connect-timeout", "30", "--progress-bar", manifest["asset_url"],
            "--output", str(part),
        ], check=True)
    if not check_asset(part, manifest)["passed"]:
        raise RuntimeError("La descarga no pasó tamaño/SHA-256; se conserva como .part.")
    part.rename(path)


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def validate(path: Path, manifest: dict) -> dict:
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(path.resolve()), "release": manifest["release"],
        "release_url": manifest["release_url"], "checks": {},
        "layer": "bronze",
        "scope": "Snapshot público oficial sin transformaciones; no incluye narrativas privadas.",
    }
    checks = report["checks"]
    checks["asset"] = check_asset(path, manifest)
    if not checks["asset"]["passed"]:
        report["passed"] = False
        return report
    print("Tamaño y SHA-256 correctos; verificando integridad y conteos...", flush=True)
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        conn.execute("PRAGMA query_only = ON")
        integrity = [r[0] for r in conn.execute("PRAGMA integrity_check")]
        checks["sqlite_integrity"] = {"result": integrity, "passed": integrity == ["ok"]}
        # Count every violation, rather than checking just a sample.
        fk_count = sum(1 for _ in conn.execute("PRAGMA foreign_key_check"))
        checks["foreign_keys"] = {"violations": fk_count, "passed": fk_count == 0}
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        report["table_counts"] = {
            t: conn.execute(f"SELECT COUNT(*) FROM {quote(t)}").fetchone()[0] for t in tables
        }
        report["schema"] = {
            t: [dict(zip(("cid", "name", "type", "notnull", "default", "pk"), r))
                for r in conn.execute(f"PRAGMA table_info({quote(t)})")]
            for t in tables
        }
        for name, expected in manifest["expected_metrics"].items():
            sql = METRICS[name]
            actual = conn.execute(sql).fetchone()[0]
            checks[name] = {"actual": actual, "expected": expected,
                            "passed": actual == expected, "sql": sql}
        sql = """SELECT d.name, COUNT(*) FROM sighting s
                 JOIN source_database d ON d.id=s.source_db_id GROUP BY d.name"""
        actual = dict(conn.execute(sql))
        checks["sources"] = {"actual": actual, "expected": manifest["expected_sources"],
                              "passed": actual == manifest["expected_sources"], "sql": sql}
        columns = {r[1] for r in conn.execute("PRAGMA table_info(sighting)")}
        raw = sorted(columns & {"description", "summary", "notes", "raw_json"})
        checks["public_export"] = {"raw_columns_present": raw, "passed": not raw}
        # Explicit relationship checks cover references even if FK declarations are absent.
        links = [
            ("sighting", "source_db_id", "source_database"),
            ("sighting", "location_id", "location"),
            ("sighting", "origin_id", "source_origin"),
            ("sighting_analysis", "sighting_id", "sighting"),
            ("duplicate_candidate", "sighting_id_a", "sighting"),
            ("duplicate_candidate", "sighting_id_b", "sighting"),
        ]
        for child, col, parent in links:
            sql = (f"SELECT COUNT(*) FROM {quote(child)} c LEFT JOIN {quote(parent)} p "
                   f"ON c.{quote(col)}=p.id WHERE c.{quote(col)} IS NOT NULL AND p.id IS NULL")
            count = conn.execute(sql).fetchone()[0]
            checks[f"orphans_{child}_{col}"] = {"actual": count, "expected": 0,
                                                  "passed": count == 0, "sql": sql}
        # These profile source quality without altering or 'fixing' the official data.
        profiles = {
            "date_event_bounds": "SELECT MIN(date_event), MAX(date_event) FROM sighting",
            "invalid_sighting_coords": "SELECT COUNT(*) FROM sighting WHERE lat NOT BETWEEN -90 AND 90 OR lng NOT BETWEEN -180 AND 180",
            "partial_sighting_coords": "SELECT COUNT(*) FROM sighting WHERE (lat IS NULL) != (lng IS NULL)",
            "missing_quality_score": "SELECT COUNT(*) FROM sighting WHERE quality_score IS NULL",
            "duplicate_source_record_groups": "SELECT COUNT(*) FROM (SELECT source_db_id, source_record_id FROM sighting WHERE source_record_id IS NOT NULL GROUP BY source_db_id, source_record_id HAVING COUNT(*)>1)",
            "analysis_missing": "SELECT COUNT(*) FROM sighting s LEFT JOIN sighting_analysis a ON a.sighting_id=s.id WHERE a.sighting_id IS NULL",
            "ufocat_century_sentinel_dates": "SELECT COUNT(*) FROM sighting s JOIN source_database d ON d.id=s.source_db_id WHERE d.name='UFOCAT' AND s.date_event LIKE '0019-%'",
        }
        report["quality_profile"] = {
            k: {"result": conn.execute(sql).fetchone(), "sql": sql} for k, sql in profiles.items()
        }
    report["passed"] = all(c["passed"] for c in checks.values())
    report["quality_notes"] = [
        "PASS acredita integridad y completitud de la publicación, no ausencia de errores en los datos originales.",
        "Coordenadas no nulas: 493879; pares dentro de los límites geográficos: 493845.",
        "UFOCAT reutiliza source_record_id: usar sighting.id como clave; no deduplicar por source_record_id.",
        "Los límites de fecha son lexicográficos: el corpus mezcla fechas completas, años y meses.",
    ]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=ROOT / "data/bronze/ufo.db",
        help="Destino del snapshot Bronze (por defecto: data/bronze/ufo.db)",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Verificar la base local sin descargar",
    )
    args = parser.parse_args()
    report_path = args.database.with_suffix(".validation.json")
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if not args.verify_only:
            download(args.database, manifest)
        report = validate(args.database, manifest)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for name, check in report["checks"].items():
        print(f"{'OK' if check['passed'] else 'FAIL'} {name}")
    if not report["passed"]:
        print(f"FAIL. Informe: {report_path}", file=sys.stderr)
        return 1
    print(f"Bronze lista: {args.database}")
    print(f"{report['table_counts']['sighting']:,} avistamientos. Informe: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
