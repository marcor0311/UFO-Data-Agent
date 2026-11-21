#!/usr/bin/env python3
"""Build and verify a traceable, cleaned Silver database from pinned Bronze."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import shutil
import subprocess
import sys
import tempfile

if __package__:
    from .build_bronze import METRICS, check_asset, digest, quote
    from .silver_quality import apply_quality, validate_quality, verify_change_ledger, Countries
else:
    from build_bronze import METRICS, check_asset, digest, quote
    from silver_quality import apply_quality, validate_quality, verify_change_ledger, Countries

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/silver.json"
MANIFEST = ROOT / "config/bronze.json"


def project_schema(sql: str, removed: set[str]) -> str:
    """Remove whole column definitions, preserving the other original SQL clauses.

    Split only commas at the table-definition level: commas inside defaults,
    constraints, quoted text and comments must remain untouched. An inline
    UNIQUE constraint disappears with its column (notably reddit_post_id).
    """
    start = sql.index("(")
    parts = []
    begin = i = start + 1
    depth = 0
    while i < len(sql):
        char = sql[i]
        if sql.startswith("--", i):
            end = sql.find("\n", i + 2)
            i = len(sql) if end < 0 else end + 1
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            if end < 0:
                raise ValueError("Comentario SQL sin cerrar")
            i = end + 2
            continue
        if char in "\"'`[":
            end_quote = "]" if char == "[" else char
            i += 1
            while i < len(sql):
                if sql[i] == end_quote:
                    if end_quote != "]" and i + 1 < len(sql) and sql[i + 1] == end_quote:
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                parts.append(sql[begin:i])
                break
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(sql[begin:i])
            begin = i + 1
        i += 1
    else:
        raise ValueError("Definición de tabla sin cerrar")

    kept = []
    found = set()
    for part in parts:
        definition = re.sub(r"\A(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/)*", "", part, flags=re.S)
        match = re.match(r'"((?:""|[^"])*)"|`((?:``|[^`])*)`|\[([^]]+)\]|([\w]+)', definition)
        if not match:
            raise ValueError(f"Definición SQL no reconocida: {definition!r}")
        name = next(value for value in match.groups() if value is not None)
        name = name.replace('""', '"').replace("``", "`")
        if name in removed:
            found.add(name)
        else:
            kept.append(part)
    if found != removed:
        raise ValueError(f"No se encontraron columnas en el esquema: {sorted(removed - found)}")
    return sql[:start + 1] + ",".join(kept) + sql[i:]


def columns(conn: sqlite3.Connection, table: str, schema: str = "main") -> list:
    return list(conn.execute(f"PRAGMA {schema}.table_info({quote(table)})"))


def lineage_for(source_hash: str, policy: dict) -> tuple[dict, dict]:
    files = [Path(__file__), Path(__file__).with_name("silver_quality.py")]
    code_hashes = {path.name: digest(path) for path in files}
    ref_path = ROOT / policy["quality"]["country_reference"]
    reference = json.loads(ref_path.read_text(encoding="utf-8"))
    policy_hash = hashlib.sha256(json.dumps(policy, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    lineage = {"bronze_sha256": source_hash, "policy_version": policy["version"],
               "policy_sha256": policy_hash, "code_sha256": code_hashes,
               "country_reference_sha256": digest(ref_path), "country_reference_source": reference["source"],
               "reference_date": policy["quality"]["reference_date"]}
    lineage["run_id"] = hashlib.sha256(json.dumps(lineage, sort_keys=True).encode()).hexdigest()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    lineage["git_base_commit"] = commit.stdout.strip() if commit.returncode == 0 else None
    return lineage, reference


def build(source: Path, target: Path, manifest: dict, policy: dict, replace: bool = False) -> dict:
    source, target = source.resolve(), target.resolve()
    report_path = target.with_suffix(".validation.json")
    if source == target or report_path == source:
        raise ValueError("Silver debe tener una ruta distinta de Bronze")
    if not replace and (target.exists() or report_path.exists()):
        raise FileExistsError(f"Se conserva la salida existente: {target} / {report_path}")
    previous = None
    if replace and (target.exists() or report_path.exists()):
        if not target.exists() or not report_path.exists():
            raise ValueError("La salida previa debe tener base e informe para reemplazarla")
        wal = target.with_name(target.name + "-wal")
        if wal.exists() and wal.stat().st_size:
            raise ValueError("Silver tiene cambios WAL; cierre el escritor antes de reemplazarla")
        previous = json.loads(report_path.read_text(encoding="utf-8"))
        if previous.get("layer") != "silver" or previous.get("sha256") != digest(target):
            raise ValueError("La salida previa no coincide con su informe; se conserva")
    # immutable=1 is safe only for the pinned, standalone snapshot, without WAL changes.
    wal = source.with_name(source.name + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("Bronze tiene cambios WAL; se requiere el snapshot independiente")
    asset = check_asset(source, manifest)
    if not asset["passed"]:
        raise ValueError("Bronze no coincide con el tamaño/SHA-256 del manifiesto")

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "layer": "silver", "policy": policy, "database": str(target),
        "source": {"database": str(source), **asset}, "checks": {},
        "removed_indexes": [], "removed_columns": {}, "table_counts": {}, "schema": {},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".silver-", dir=target.parent) as work:
        output = Path(work) / "ufo.db"
        with closing(sqlite3.connect(output, uri=True)) as conn:
            conn.execute("ATTACH DATABASE ? AS bronze", (source.as_uri() + "?mode=ro&immutable=1",))
            tables = dict(conn.execute(
                "SELECT name, sql FROM bronze.sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ))
            if set(policy["drop_columns"]) - tables.keys():
                raise ValueError("La política menciona tablas ausentes de Bronze")
            if conn.execute("SELECT 1 FROM bronze.sqlite_master WHERE type IN ('view','trigger') LIMIT 1").fetchone():
                raise ValueError("Revisar vistas/triggers antes de transformar este esquema")

            layouts = {}
            for table in tables:
                layout = columns(conn, table, "bronze")
                removed = set(policy["drop_columns"].get(table, []))
                names = {col[1] for col in layout}
                if removed - names:
                    raise ValueError(f"Columnas ausentes de {table}: {sorted(removed - names)}")
                if any(col[5] and col[1] in removed for col in layout):
                    raise ValueError(f"No se puede eliminar una clave primaria de {table}")
                # Only NULL and genuinely blank text count as empty. Zero, [], {},
                # 'unknown' and other sentinels are information and stop the build.
                if removed:
                    predicates = [
                        f"({quote(col)} IS NOT NULL AND NOT (typeof({quote(col)})='text' "
                        f"AND length(trim({quote(col)}, char(9)||char(10)||char(11)||char(12)||char(13)||' '))=0))"
                        for col in sorted(removed)
                    ]
                    sql = f"SELECT 1 FROM bronze.{quote(table)} WHERE " + " OR ".join(predicates) + " LIMIT 1"
                    if conn.execute(sql).fetchone():
                        raise ValueError(f"Se conserva Bronze: alguna candidata de {table} contiene datos")
                    report["removed_columns"][table] = sorted(removed)
                layouts[table] = [col for col in layout if col[1] not in removed]

            print("Bronze verificada; creando Silver con las columnas retenidas...", flush=True)
            with conn:
                for table, sql in tables.items():
                    removed = set(policy["drop_columns"].get(table, []))
                    conn.execute(project_schema(sql, removed) if removed else sql)
                    expected = [(c[1], *c[2:]) for c in layouts[table]]
                    if [(c[1], *c[2:]) for c in columns(conn, table)] != expected:
                        raise ValueError(f"El esquema proyectado de {table} no coincide")
                    retained = ", ".join(quote(col[1]) for col in layouts[table])
                    conn.execute(f"INSERT INTO main.{quote(table)} ({retained}) SELECT {retained} FROM bronze.{quote(table)}")
                if conn.execute("SELECT 1 FROM bronze.sqlite_master WHERE name='sqlite_sequence'").fetchone():
                    conn.execute("DELETE FROM main.sqlite_sequence")
                    conn.execute("INSERT INTO main.sqlite_sequence SELECT * FROM bronze.sqlite_sequence")
                for name, table, sql in conn.execute(
                    "SELECT name, tbl_name, sql FROM bronze.sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"
                ).fetchall():
                    indexed = {row[2] for row in conn.execute(f"PRAGMA bronze.index_info({quote(name)})")}
                    if indexed & set(policy["drop_columns"].get(table, [])):
                        report["removed_indexes"].append(name)
                    else:
                        conn.execute(sql)

            conn.execute("PRAGMA foreign_keys=ON")
            checks = report["checks"]
            integrity = [row[0] for row in conn.execute("PRAGMA main.integrity_check")]
            checks["sqlite_integrity"] = {"result": integrity, "passed": integrity == ["ok"]}
            violations = sum(1 for _ in conn.execute("PRAGMA main.foreign_key_check"))
            checks["foreign_keys"] = {"violations": violations, "passed": violations == 0}
            for table, layout in layouts.items():
                original = conn.execute(f"SELECT COUNT(*) FROM bronze.{quote(table)}").fetchone()[0]
                actual = conn.execute(f"SELECT COUNT(*) FROM main.{quote(table)}").fetchone()[0]
                report["table_counts"][table] = actual
                report["schema"][table] = [dict(zip(("cid", "name", "type", "notnull", "default", "pk"), row)) for row in columns(conn, table)]
                checks[f"rows_{table}"] = {"actual": actual, "expected": original, "passed": actual == original}
                keys = [col[1] for col in layout if col[5]]
                if not keys:
                    raise ValueError(f"Falta clave primaria para verificar los valores de {table}")
                join = " AND ".join(f"s.{quote(key)} IS b.{quote(key)}" for key in keys)
                equal = " AND ".join(f"s.{quote(col[1])} IS b.{quote(col[1])}" for col in layout)
                sql = f"SELECT COUNT(*) FROM main.{quote(table)} s LEFT JOIN bronze.{quote(table)} b ON {join} WHERE b.{quote(keys[0])} IS NULL OR NOT ({equal})"
                changed = conn.execute(sql).fetchone()[0]
                checks[f"values_{table}"] = {"phase": "projection_before_quality", "changed_rows": changed, "passed": changed == 0, "sql": sql}
            for name, expected in manifest.get("expected_metrics", {}).items():
                actual = conn.execute(METRICS[name]).fetchone()[0]
                checks[name] = {"actual": actual, "expected": expected, "passed": actual == expected}
            if "expected_sources" in manifest:
                actual = dict(conn.execute("SELECT d.name, COUNT(*) FROM sighting s JOIN source_database d ON d.id=s.source_db_id GROUP BY d.name"))
                checks["sources"] = {"actual": actual, "expected": manifest["expected_sources"], "passed": actual == manifest["expected_sources"]}

            if policy.get("quality"):
                lineage, reference = lineage_for(asset["sha256"], policy)
                report["lineage"] = lineage
                print("Proyección verificada; aplicando reglas de calidad...", flush=True)
                report["quality"], quality_checks = apply_quality(conn, policy["quality"], reference, lineage, layouts)
                checks.update(quality_checks)
                report["metrics_after_quality"] = {name: conn.execute(METRICS[name]).fetchone()[0] for name in manifest.get("expected_metrics", {})}
                report["support_table_counts"] = {
                    row[0]: conn.execute(f"SELECT COUNT(*) FROM {quote(row[0])}").fetchone()[0]
                    for row in conn.execute("SELECT name FROM main.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                    if row[0] not in layouts
                }
                report["schema"] = {
                    table: [dict(zip(("cid", "name", "type", "notnull", "default", "pk"), row)) for row in columns(conn, table)]
                    for table in layouts
                }

        checks["bronze_unchanged"] = check_asset(source, manifest)
        report["passed"] = all(check["passed"] for check in checks.values())
        if not report["passed"]:
            failures = [name for name, check in checks.items() if not check["passed"]]
            raise ValueError(f"Silver no pasó las verificaciones: {', '.join(failures)}")
        report["size_bytes"] = output.stat().st_size
        report["sha256"] = digest(output)
        temp_report = Path(work) / "validation.json"
        temp_report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if previous:
            if digest(target) != previous["sha256"]:
                raise ValueError("Silver cambió durante la construcción; se conserva")
            archive = target.parent / ".history" / previous["sha256"]
            archive.mkdir(parents=True, exist_ok=True)
            for original in (target, report_path):
                backup = archive / original.name
                # Identical database bytes may have validation reports from
                # different runs. Retain each report without an archive collision.
                if original == report_path and backup.exists() and digest(backup) != digest(original):
                    backup = archive / f"{original.stem}.{digest(original)[:16]}{original.suffix}"
                if backup.exists():
                    if digest(backup) != digest(original):
                        raise ValueError(f"Historial distinto del archivo actual: {backup}")
                else:
                    shutil.copy2(original, backup)
            os.replace(output, target)
            os.replace(temp_report, report_path)
        else:
            # Hard links publish only complete files and refuse existing outputs.
            os.link(output, target)
            os.link(temp_report, report_path)
    return report


def verify(source: Path, target: Path, manifest: dict, policy: dict) -> dict:
    for path in (source, target):
        wal = path.with_name(path.name + "-wal")
        if wal.exists() and wal.stat().st_size:
            raise ValueError(f"El snapshot tiene cambios WAL: {path}")
    report = json.loads(target.with_suffix(".validation.json").read_text(encoding="utf-8"))
    if not check_asset(source, manifest)["passed"] or digest(target) != report["sha256"]:
        raise ValueError("Bronze o Silver no coinciden con sus SHA-256 registrados")
    if report["policy"] != policy:
        raise ValueError("Silver se generó con una política distinta de la actual")
    lineage, reference = lineage_for(manifest["sha256"], policy)
    if lineage["run_id"] != report["lineage"]["run_id"]:
        raise ValueError("El código o el catálogo cambiaron desde la construcción de Silver")
    with closing(sqlite3.connect(target.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        conn.execute("ATTACH DATABASE ? AS bronze", (source.resolve().as_uri() + "?mode=ro&immutable=1",))
        layouts = {}
        for table in report["table_counts"]:
            layouts[table] = [col for col in columns(conn, table, "bronze") if col[1] not in policy["drop_columns"].get(table, [])]
            count = conn.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0]
            original = conn.execute(f"SELECT COUNT(*) FROM bronze.{quote(table)}").fetchone()[0]
            if count != original or count != report["table_counts"][table]:
                raise ValueError(f"Conteo distinto de Bronze en {table}")
        changed = verify_change_ledger(conn, layouts)
        checks = validate_quality(conn, policy["quality"], Countries(reference))
        if not all(check["passed"] for check in checks.values()):
            raise ValueError("Silver no pasa las reglas de calidad")
    return {"passed": True, "checks": len(checks), "changed_fields_verified": changed, "run_id": lineage["run_id"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/bronze/ufo.db", help="Snapshot Bronze local")
    parser.add_argument("--database", type=Path, default=ROOT / "data/silver/ufo.db", help="Destino nuevo de Silver")
    parser.add_argument("--replace", action="store_true", help="Reemplazar Silver validada, conservando la anterior en .history")
    parser.add_argument("--verify-only", action="store_true", help="Revisar Silver existente sin modificarla")
    args = parser.parse_args()
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        if args.verify_only:
            print(json.dumps(verify(args.source, args.database, manifest, policy), indent=2))
            return 0
        report = build(args.source, args.database, manifest, policy, replace=args.replace)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    removed = sum(len(cols) for cols in report["removed_columns"].values())
    print(f"Silver lista: {args.database}; {removed} columnas eliminadas.")
    print(f"Informe: {args.database.with_suffix('.validation.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
