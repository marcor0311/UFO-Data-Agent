"""Shared, side-effect free helpers for the Gold layer (paths, catalogs, hashes)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/gold/gold.json"
CONFIG = ROOT / "config/gold"


def digest(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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
    recording a verification must not change the load it verifies.
    """
    files = {name: digest(root / name) for name in sorted(policy["definitions"])}
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
