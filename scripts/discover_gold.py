#!/usr/bin/env python3
"""Verify Gold, profile it and materialize the read-only serving cache.

Run once per Gold load, never inside a conversation, on a version directory
that has no serving cache yet (a published cache is never replaced). Writes,
inside that version:
  serving/ufo_gold_serving.db (+ .manifest.json with cache_version and SHA-256)
  docs/GOLD_CATALOG.json, docs/GOLD_CATALOG.md, docs/GOLD_ENTITIES.json

The versioned copies in docs/ change only with
``python scripts/build_all.py --actualizar-referencias``.

    discover_gold.py --version DIR
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

if __package__:
    from .gold_common import ROOT, definitions_digest, digest, load_catalogs, load_json, load_policy, normalize, text_digest
    from .pipeline_context import write_text
    from . import releases
else:
    from gold_common import ROOT, definitions_digest, digest, load_catalogs, load_json, load_policy, normalize, text_digest
    from pipeline_context import write_text
    import releases

SERVING_INDEXES = {
    "fact_report": ["source_code", "event_year", "year_month", "event_date", "country_iso2", "shape_code", "color_code",
                    "duration_bucket", "duplicate_status", "nearest_facility_key", "distance_band", "origin_code",
                    "usable_for_map", "cell5_lat", "weekday"],
    "report_model_output": ["source_code", "event_year", "country_iso2"],
    "fact_event": ["event_year", "country_iso2"],
    "event_report": ["canonical_event_id"],
    "agg_spatial_cell": ["resolution_deg"],
    "agg_coverage": ["aggregate_code"],
}
RELATIONSHIPS = [
    "fact_report.report_id es el ID de sighting en Bronze y Silver (una fila por informe).",
    "report_model_output.report_id = fact_report.report_id (1:1).",
    "fact_event.canonical_event_id = fact_report.report_id del representante; event_report enlaza cada miembro con su evento.",
    "fact_report.source_code → dim_source; origin_code → dim_origin; collection_code → dim_collection.",
    "fact_report.date_key → dim_date (fecha a su precisión segura: AAAA, AAAA-MM o AAAA-MM-DD).",
    "fact_report.country_iso2 → dim_country; shape_code → dim_shape; color_code → dim_color; duration_bucket → dim_duration_bucket; movement_type → dim_movement.",
    "fact_report.nearest_facility_key → dim_nuclear_facility; distance_band → dim_distance_band.",
    "agg_* se derivan de fact_report con el filtro de elegibilidad declarado en dataset_catalog.json; agg_coverage explica incluidos y excluidos de cada agregado.",
]


def profile_table(conn, table: str, max_values: int = 60) -> dict:
    rows = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    columns = {}
    for _, name, declared, *_ in conn.execute(f'PRAGMA table_info("{table}")').fetchall():
        col = f'"{name}"'
        nulls, distinct, low, high = conn.execute(
            f"SELECT COUNT(*)-COUNT({col}), COUNT(DISTINCT {col}), MIN({col}), MAX({col}) FROM \"{table}\"").fetchone()
        types = sorted(t for (t,) in conn.execute(f'SELECT DISTINCT typeof({col}) FROM "{table}" WHERE {col} IS NOT NULL'))
        p = {"declared_type": declared, "types": types, "nulls": nulls, "distinct_count": distinct}
        if types and set(types) <= {"integer", "real"}:
            p.update(min=low, max=high)
        elif types == ["text"] and distinct > max_values:
            p.update(min=low, max=high)
        if 0 < distinct <= max_values:
            p["values"] = [{"value": v, "rows": n} for v, n in conn.execute(
                f'SELECT {col}, COUNT(*) FROM "{table}" WHERE {col} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1')]
        columns[name] = p
    return {"rows": rows, "columns": columns}


def labels_and_values(conn, catalogs: dict) -> tuple[dict, dict]:
    dims = catalogs["dimensions"]
    labels: dict = {}
    values: dict = {}
    table_labels = {"source_code": "SELECT source_code, label_es FROM dim_source",
                    "origin_code": "SELECT origin_code, label_es FROM dim_origin",
                    "collection_code": "SELECT collection_code, label_es FROM dim_collection",
                    "country_iso2": "SELECT country_iso2, name_es FROM dim_country",
                    "shape_code": "SELECT shape_code, label_es FROM dim_shape",
                    "color_code": "SELECT color_code, label_es FROM dim_color",
                    "color_family": "SELECT DISTINCT family_code, family_label_es FROM dim_color",
                    "duration_bucket": "SELECT duration_bucket, label_es FROM dim_duration_bucket",
                    "movement_type": "SELECT movement_type, label_es FROM dim_movement",
                    "nearest_facility_key": "SELECT nearest_facility_key, name FROM dim_nuclear_facility",
                    "distance_band": "SELECT distance_band, label_es FROM dim_distance_band"}
    for column, sql in table_labels.items():
        labels[column] = {str(k): v for k, v in conn.execute(sql)}
        values[column] = sorted(labels[column])
    for column in ("hynek", "emotion_7_dominant"):
        table = "fact_report" if column == "hynek" else "report_model_output"
        values[column] = sorted(v for (v,) in conn.execute(f'SELECT DISTINCT "{column}" FROM {table} WHERE "{column}" IS NOT NULL'))
    for column in ("aggregate_code", "eligibility_code"):
        values[column] = sorted(v for (v,) in conn.execute(f'SELECT DISTINCT "{column}" FROM agg_coverage'))
    values["date_key"] = sorted(v for (v,) in conn.execute("SELECT date_key FROM dim_date"))
    reasons = dims["exclusion_reasons"]
    for column in ("reason", "calendar_exclusion", "month_exclusion", "day_exclusion", "hour_exclusion",
                   "map_exclusion", "country_exclusion", "proximity_exclusion"):
        labels[column] = dict(reasons)
        values[column] = sorted(reasons)
    for code, dim in dims["dimensions"].items():
        if dim["kind"] in ("enum", "integer_enum"):
            labels[code] = dict(dim["values"])
        elif dim["kind"] == "flag":
            labels[code] = {"0": "no", "1": "sí"}
    labels["aggregate_code"] = {k: catalogs["datasets"][k]["label"] for k in values["aggregate_code"]}
    return labels, values


def entities(conn, catalogs: dict, load_id: str, root: Path = ROOT) -> dict:
    labels = catalogs["dimensions"]["labels"]
    countries = load_json(root / "config/countries.json")
    inverse: dict = {}
    for alias, code in countries["aliases"].items():
        inverse.setdefault(code, []).append(alias.title())
    aliases_es = catalogs["countries_es"]["aliases_es"]

    def unique(items):
        return sorted({i for i in items if i})
    sources = [{"id": code, "canonical_name": code, "display_name": label, "aliases": unique([code, *aliases]),
                "report_count": n, "collection_code": coll, "calendar_year_min": lo, "calendar_year_max": hi}
               for code, label, n, coll, lo, hi in conn.execute(
                   "SELECT source_code, label_es, report_count, collection_code, calendar_year_min, calendar_year_max FROM dim_source ORDER BY source_code")
               for aliases in [labels["source_code"][code][1]]]
    origins = [{"id": code, "canonical_name": code, "display_name": label, "aliases": unique([code, label]), "report_count": n}
               for code, label, n in conn.execute("SELECT origin_code, label_es, report_count FROM dim_origin ORDER BY origin_code")]
    collections = [{"id": code, "canonical_name": code, "display_name": label, "aliases": unique([code, label])}
                   for code, label in conn.execute("SELECT collection_code, label_es FROM dim_collection ORDER BY 1")]
    country_items = [{"id": code, "canonical_name": en, "display_name": es,
                      "aliases": unique([code, alpha3, en, es, *inverse.get(code, []), *aliases_es.get(code, [])]),
                      "alpha3": alpha3, "report_count": n}
                     for code, alpha3, en, es, n in conn.execute(
                         "SELECT country_iso2, alpha3, name_en, name_es, report_count FROM dim_country ORDER BY country_iso2")]
    shapes = [{"id": code, "canonical_name": code, "display_name": label, "aliases": unique([code, label])}
              for code, label in conn.execute("SELECT shape_code, label_es FROM dim_shape ORDER BY 1")]
    colors = [{"id": code, "canonical_name": code, "display_name": label, "aliases": unique([code, label]), "family_code": fam}
              for code, label, fam in conn.execute("SELECT color_code, label_es, family_code FROM dim_color ORDER BY 1")]
    facilities = [{"id": key, "canonical_name": name, "display_name": name, "aliases": unique([name, key]),
                   "facility_ids": json.loads(ids), "facility_types": json.loads(types), "latitude": lat, "longitude": lng,
                   "nearest_reports": n}
                  for key, name, ids, types, lat, lng, n in conn.execute(
                      "SELECT nearest_facility_key, name, facility_ids, facility_types, latitude, longitude, nearest_reports FROM dim_nuclear_facility ORDER BY 1")]
    return {"load_id": load_id,
            "description": "Entidades resolubles por el agente: ID real (código usado en filtros), nombre canónico, alias y nombre de visualización en español.",
            "regions_note": "Silver no publica regiones por informe; las etiquetas multinacionales del catálogo original solo detectan contradicciones. No hay entidades de región.",
            "sources": sources, "origins": origins, "collections": collections, "countries": country_items,
            "shapes": shapes, "colors": colors, "nuclear_facilities": facilities, "regions": []}


def num(value) -> str:
    """Spanish thousands separator."""
    return f"{value:,}".replace(",", ".")


def markdown(catalog: dict, coverage: list, sources: list) -> str:
    lines = ["# Catálogo Gold (autogenerado)", "",
             "Generado por `scripts/discover_gold.py`; no editar a mano.", "",
             f"- Carga Gold (`load_id`): `{catalog['load_id']}`",
             f"- SHA-256 de Gold: `{catalog['manifest']['gold_sha256']}`",
             f"- SHA-256 de Silver: `{catalog['manifest']['silver']['sha256']}`",
             f"- SHA-256 de Bronze: `{catalog['manifest']['bronze']['sha256']}`",
             f"- Hash de definiciones: `{catalog['manifest']['definitions_sha256']}`",
             f"- Construida: {catalog['manifest']['built_at']}", "",
             "## Tablas", "", "| Tabla | Filas | Columnas | Grano |", "|---|---:|---:|---|"]
    for name, profile in catalog["profiles"].items():
        grain = catalog["dataset_catalog"].get(name, {}).get("grain", "dimensión")
        lines.append(f"| `{name}` | {num(profile['rows'])} | {len(profile['columns'])} | {grain} |")
    lines += ["", "Tipos, nulos, rangos, valores categóricos y conteos por columna: [GOLD_CATALOG.json](GOLD_CATALOG.json).", "",
              "## Informes por fuente", "", "| Fuente | Informes | Sin candidatos pendientes | Con candidato pendiente | Con evidencia externa |",
              "|---|---:|---:|---:|---:|"]
    for row in sources:
        lines.append("| {} | ".format(row[0]) + " | ".join(num(v) for v in row[1:]) + " |")
    lines += ["", "## Cobertura de cada agregado", "", "| Agregado | Elegibilidad | Incluidos | Excluidos |", "|---|---|---:|---:|"]
    for row in coverage:
        lines.append("| `{}` | {} | ".format(*row[:2]) + " | ".join(num(v) for v in row[2:]) + " |")
    lines += ["", "## Métricas", "", "| Código | Etiqueta | Tipo | Cota de duplicados | Datasets |", "|---|---|---|---|---|"]
    for code, m in catalog["metric_catalog"].items():
        bound = m.get("duplicate_bound", {}).get("role", "—")
        lines.append(f"| `{code}` | {m['label']} | {m['type']} | {bound} | {', '.join(sorted(m['datasets']))} |")
    lines += ["", "## Relaciones", ""] + [f"- {r}" for r in catalog["relationships"]]
    lines += ["", "## Limitaciones", ""] + [f"- **{l['code']}**: {l['text']}" for l in catalog["limitations"]]
    return "\n".join(lines) + "\n"


def discover(root: Path = ROOT, gold: Path | None = None, serving: Path | None = None, docs: Path | None = None) -> dict:
    """Materialize the serving cache and catalog docs of one Gold version.

    ``gold`` defaults to the approved version; ``serving`` and ``docs`` to its
    ``serving/`` and ``docs/`` folders. An existing cache is never replaced.
    """
    policy = load_policy(root)
    catalogs = load_catalogs(root)
    if gold is None:
        current = releases.layout(releases.data_root(root), "gold")
        if current is None:
            raise ValueError("No hay una carga Gold aprobada; indica --version DIR")
        gold = current.database
    gold = Path(gold)
    layout = releases.GoldLayout(gold.parent)
    serving = Path(serving or layout.serving)
    docs = Path(docs or layout.docs)
    if serving.exists():
        raise ValueError(f"Se conserva {serving}: una caché publicada no se reemplaza; construye una versión nueva")
    manifest = json.loads(gold.with_name(gold.stem + ".manifest.json").read_text(encoding="utf-8"))
    if digest(gold) != manifest["gold_sha256"]:
        raise ValueError("Checksum Gold incorrecto")
    definitions_sha, _ = definitions_digest(policy, root)
    if definitions_sha != manifest["definitions_sha256"]:
        raise ValueError("Las definiciones Gold cambiaron desde la construcción; ejecuta scripts/build_all.py --desde gold")
    serving.parent.mkdir(parents=True, exist_ok=True)
    building = serving.with_name(serving.name + ".building")
    if building.exists():
        os.chmod(building, stat.S_IWUSR | stat.S_IRUSR)
        building.unlink()
    with closing(sqlite3.connect(gold.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as source, \
            closing(sqlite3.connect(building)) as target:
        source.backup(target)
    with closing(sqlite3.connect(building)) as conn:
        conn.execute("PRAGMA journal_mode=OFF")
        for table, columns in SERVING_INDEXES.items():
            for column in columns:
                conn.execute(f'CREATE INDEX IF NOT EXISTS "srv_{table}_{column}" ON "{table}" ("{column}")')
        profiles = {name: profile_table(conn, name) for (name,) in
                    conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()}
        labels, values = labels_and_values(conn, catalogs)
        entity_doc = entities(conn, catalogs, manifest["load_id"], root)
        limitations = load_json(root / "config/gold/dataset_catalog.json")["limitations"]
        catalog = {"cache_version": policy["serving"]["cache_version"], "load_id": manifest["load_id"], "manifest": manifest,
                   "dataset_catalog": catalogs["datasets"], "metric_catalog": catalogs["metrics"],
                   "dimension_catalog": {k: catalogs["dimensions"][k] for k in ("eligibility", "exclusion_reasons", "dimensions")},
                   "limitations": limitations, "relationships": RELATIONSHIPS, "labels": labels, "allowed_values": values,
                   "profiles": profiles,
                   "entities": {k: entity_doc[k] for k in ("sources", "origins", "collections", "countries", "shapes", "colors", "nuclear_facilities")}}
        conn.execute("CREATE TABLE metadata (catalog TEXT NOT NULL)")
        conn.execute("INSERT INTO metadata VALUES (?)", (json.dumps(catalog, ensure_ascii=False),))
        conn.commit()
        conn.execute("ANALYZE")
        conn.commit()
        coverage = conn.execute("""SELECT aggregate_code, eligibility_code, SUM(CASE WHEN coverage_status='included' THEN report_count ELSE 0 END),
            SUM(CASE WHEN coverage_status='excluded' THEN report_count ELSE 0 END) FROM agg_coverage GROUP BY 1,2 ORDER BY 1""").fetchall()
        sources = conn.execute("""SELECT source_code, SUM(report_count), SUM(report_count_excl_candidates), SUM(pending_candidate_reports),
            SUM(external_evidence_reports) FROM agg_source GROUP BY 1 ORDER BY 1""").fetchall()
    if serving.exists():
        raise ValueError(f"Otro proceso publicó {serving} durante la construcción")
    os.replace(building, serving)
    # Read-only after the rename: Windows refuses to rename some read-only files.
    os.chmod(serving, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    serving_manifest = {"cache_version": policy["serving"]["cache_version"], "sha256": digest(serving),
                        "load_id": manifest["load_id"], "gold_sha256": manifest["gold_sha256"],
                        "catalog_sha256": text_digest(catalog)}
    write_text(serving.with_name(serving.stem + ".manifest.json"), json.dumps(serving_manifest, indent=2) + "\n")
    public = {k: catalog[k] for k in ("load_id", "manifest", "dataset_catalog", "metric_catalog", "dimension_catalog",
                                      "limitations", "relationships", "profiles")}
    public["profiles"] = {name: p for name, p in profiles.items()}
    docs.mkdir(parents=True, exist_ok=True)
    write_text(docs / "GOLD_CATALOG.json", json.dumps(public, ensure_ascii=False, indent=1) + "\n")
    write_text(docs / "GOLD_CATALOG.md", markdown(catalog, coverage, sources))
    write_text(docs / "GOLD_ENTITIES.json", json.dumps(entity_doc, ensure_ascii=False, indent=1) + "\n")
    return serving_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", type=Path, help="Directorio de versión Gold sin caché (por defecto, la aprobada)")
    args = parser.parse_args()
    try:
        result = discover(gold=releases.GoldLayout(args.version).database if args.version else None)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        print(f"CACHÉ NO GENERADA: {exc}", file=sys.stderr)
        return 1
    print(f"Caché de servicio v{result['cache_version']} para la carga {result['load_id']}: {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
