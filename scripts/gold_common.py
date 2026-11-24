"""Shared, side-effect free helpers for the Gold layer (custody, catalogs, hashes)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata

if __package__:
    from .pipeline_context import digest, text_digest_file
else:
    from pipeline_context import digest, text_digest_file

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/gold/gold.json"
CONFIG = ROOT / "config/gold"
SHA256 = re.compile(r"[0-9a-f]{64}")
# Lineage fields that only describe the run, not the recipe.
LINEAGE_INFORMATIVE = {"git_base_commit"}


def pending_wal(path: Path) -> bool:
    """True if a SQLite file has uncommitted pages in its WAL (not a standalone snapshot)."""
    path = Path(path)
    wal = path.with_name(path.name + "-wal")
    return wal.exists() and wal.stat().st_size > 0


def _silver_modules():
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    import build_bronze
    import build_silver
    return build_bronze, build_silver


def silver_provenance(silver_path: Path, bronze_path: Path, bronze_manifest: Path) -> dict:
    """Chain of custody Bronze → Silver, checked before Gold reads Silver.

    SHA-256 is not a fixed pin for Silver (it is rebuilt on every machine) but
    proof that each layer is the one its predecessor produced and validated.
    Every condition is required; a missing, empty or malformed report fails:

    * Neither snapshot has pending pages in a WAL file.
    * Bronze is the official asset: size and SHA-256 of ``config/bronze.json``
      (the same ``check_asset`` control the Bronze and Silver builds use).
    * The report is an object with ``layer="silver"`` and ``passed`` exactly
      ``true``, and records the SHA-256 (and size) of the file it validated.
    * Silver is byte-identical to that file (not modified, truncated or swapped).
    * Its lineage is complete and points to this Bronze and to the current
      recipe: every field the present repository would write (policy, code and
      reference hashes, run_id) matches, and so do its source and policy.
    """
    build_bronze, build_silver = _silver_modules()
    silver_path, bronze_path = Path(silver_path), Path(bronze_path)
    report_path = silver_path.with_suffix(".validation.json")
    result = {"passed": False, "problems": [], "silver_sha256": None, "bronze_sha256": None,
              "silver_run_id": None, "report": str(report_path)}
    problems = result["problems"]
    for label, path in (("Silver", silver_path), ("Bronze", bronze_path)):
        if not path.is_file():
            problems.append(f"falta {label}: {path}")
        elif pending_wal(path):
            problems.append(f"{label} tiene cambios pendientes en WAL ({path.name}-wal); "
                            "cierra el programa que la tiene abierta antes de consumirla")
    if problems:
        return result
    manifest = load_json(bronze_manifest)
    asset = build_bronze.check_asset(bronze_path, manifest)
    result["bronze_sha256"] = asset["sha256"]
    if not asset["passed"]:
        problems.append(f"Bronze no es el snapshot oficial: {asset['size_bytes']} bytes y SHA {asset['sha256'][:12]} "
                        f"(se esperaba {asset['expected_size_bytes']} bytes y {asset['expected_sha256'][:12]})")
    silver_sha = result["silver_sha256"] = digest(silver_path)
    try:
        report = load_json(report_path)
    except (OSError, ValueError):
        report = None
        problems.append(f"falta o es ilegible {report_path.name}")
    else:
        if not isinstance(report, dict) or not report:
            problems.append(f"{report_path.name} está vacío o mal formado")
            report = None
    if report is None:
        return result
    if report.get("layer") != "silver":
        problems.append("el informe no pertenece a la capa Silver")
    if report.get("passed") is not True:
        problems.append("la validación de Silver no fue aprobada")
    recorded = report.get("sha256")
    if not isinstance(recorded, str) or not SHA256.fullmatch(recorded):
        problems.append("el informe no registra el SHA-256 del archivo que validó")
    elif recorded != silver_sha:
        problems.append("Silver no es el archivo que validó su build (modificado o sustituido)")
    if "size_bytes" in report and report["size_bytes"] != silver_path.stat().st_size:
        problems.append("Silver no tiene el tamaño que registró su informe (modificado o truncado)")
    source = report.get("source")
    if not isinstance(source, dict) or source.get("sha256") != manifest["sha256"] \
            or source.get("size_bytes", manifest.get("size_bytes")) != manifest.get("size_bytes"):
        problems.append("Silver se construyó desde otra Bronze (el informe no registra la Bronze oficial)")
    lineage = report.get("lineage")
    if not isinstance(lineage, dict):
        problems.append("el informe no registra el linaje de Silver")
        return result
    result["silver_run_id"] = lineage.get("run_id")
    if lineage.get("bronze_sha256") != manifest["sha256"]:
        problems.append("Silver se construyó desde otra Bronze")
    policy = json.loads(build_silver.POLICY.read_text(encoding="utf-8"))
    current, _ = build_silver.lineage_for(manifest["sha256"], policy)
    recipe = [k for k in current if k not in LINEAGE_INFORMATIVE]
    missing = [k for k in recipe if k not in lineage]
    if missing:
        problems.append(f"linaje de Silver incompleto: faltan {', '.join(missing)}")
    changed = [k for k in recipe if k in lineage and k != "bronze_sha256" and lineage[k] != current[k]]
    if report.get("policy") != policy:
        changed.append("policy")
    if changed:
        problems.append(f"Silver está desactualizada: cambió su política, código o referencias ({', '.join(changed)})")
    result["passed"] = not problems
    return result


def text_digest(value) -> str:
    """SHA-256 of a canonical JSON rendering (sorted keys, no whitespace)."""
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_policy(root: Path = ROOT) -> dict:
    return load_json(root / "config/gold/gold.json")


def load_catalogs(root: Path = ROOT) -> dict:
    folder = root / "config/gold"
    return {
        "datasets": load_json(folder / "dataset_catalog.json")["datasets"],
        "metrics": load_json(folder / "metric_catalog.json")["metrics"],
        "dimensions": load_json(folder / "dimension_catalog.json"),
        "countries_es": load_json(folder / "country_names_es.json"),
    }


def definitions_digest(policy: dict, root: Path = ROOT) -> tuple[str, dict]:
    """Hash of every file that defines the Gold load (code, policy and catalogs).

    Certified queries, corrections and evaluations are excluded on purpose:
    recording a verification must not change the load it verifies. Line
    endings are normalised, so a CRLF checkout yields the same hash.
    """
    files = {name: text_digest_file(root / name) for name in sorted(policy["definitions"])}
    return text_digest(files), files


def load_id_for(policy: dict, silver_sha: str, bronze_sha: str, definitions_sha: str) -> str:
    """Deterministic identifier: same inputs and definitions → same load."""
    return text_digest({"gold_version": policy["gold_version"], "silver_sha256": silver_sha,
                        "bronze_sha256": bronze_sha, "definitions_sha256": definitions_sha})


def connect_readonly(path: Path, immutable: bool = True) -> sqlite3.Connection:
    """Read-only connection that never creates journal, WAL or SHM files."""
    uri = Path(path).resolve().as_uri() + "?mode=ro" + ("&immutable=1" if immutable else "")
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=1")
    return conn


def normalize(text: str) -> str:
    """Accent- and case-insensitive key used for entity aliases."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(plain.casefold().replace(".", " ").replace("-", " ").split())


def eligibility_flags(policy: dict) -> dict:
    return {code: spec["flag"] for code, spec in policy["eligibility"].items()}
