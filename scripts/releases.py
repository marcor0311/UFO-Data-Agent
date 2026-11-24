"""Versioned publication of Silver and Gold through a local SQLite catalog.

Every build writes into a new candidate directory with a unique name
(``<data>/<layer>/versions/<UTC>-<pid>-<random>/``) and never touches a
published file. Once every control has passed, the candidate is promoted by a
single transaction on ``<data>/releases.sqlite3``: one row changes from the
previous version to the new one. Until that commit the previous approved
version stays current; a failure or interruption leaves at most an orphan
candidate, which the next successful build removes.

Readers (the API, the CLIs) resolve the approved version from the catalog and
check that its ``release.json`` is exactly the one that was promoted. Files
outside the catalog, such as the pre-catalog ``data/gold/ufo_gold.db``, are
never adopted as current.

The build lock is an exclusive SQLite transaction on ``<data>/.build.lock``:
the same file-locking primitive as the catalog, released by the operating
system if the process dies, on macOS, Linux and Windows alike.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import stat

if __package__:
    from .pipeline_context import digest, write_text
else:
    from pipeline_context import digest, write_text

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "releases.sqlite3"
LOCK = ".build.lock"
LAYERS = ("silver", "gold")
# Files that may change after promotion without affecting the load.
UNTRACKED = {"release.json", "build.metrics.json", ".candidate"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS version (
    layer TEXT NOT NULL CHECK (layer IN ('silver', 'gold')),
    version TEXT NOT NULL,
    directory TEXT NOT NULL,
    identity TEXT NOT NULL,
    release_sha256 TEXT NOT NULL,
    parent_version TEXT,
    registered_at TEXT NOT NULL,
    PRIMARY KEY (layer, version));
CREATE TABLE IF NOT EXISTS approved (
    layer TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    promoted_at TEXT NOT NULL,
    FOREIGN KEY (layer, version) REFERENCES version (layer, version));
CREATE TABLE IF NOT EXISTS promotion (
    id INTEGER PRIMARY KEY,
    layer TEXT NOT NULL,
    version TEXT NOT NULL,
    previous_version TEXT,
    promoted_at TEXT NOT NULL);
"""


class ReleaseError(RuntimeError):
    pass


class BuildLocked(ReleaseError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def data_root(root: Path = ROOT) -> Path:
    """Data directory: ``UFO_DATA_DIR`` if set, otherwise ``<repo>/data``."""
    value = os.environ.get("UFO_DATA_DIR")
    return Path(value).expanduser().resolve() if value else Path(root) / "data"


def bronze_path(data: Path) -> Path:
    return Path(data) / "bronze" / "ufo.db"


# -- layouts -----------------------------------------------------------------
@dataclass(frozen=True)
class SilverLayout:
    directory: Path

    @property
    def database(self) -> Path:
        return self.directory / "ufo.db"

    @property
    def validation(self) -> Path:
        return self.directory / "ufo.validation.json"

    @property
    def readiness(self) -> Path:
        return self.directory / "ufo.readiness.json"

    @property
    def review(self) -> Path:
        return self.directory / "ufo.review.json"

    @property
    def release(self) -> Path:
        return self.directory / "release.json"


@dataclass(frozen=True)
class GoldLayout:
    directory: Path

    @property
    def database(self) -> Path:
        return self.directory / "ufo_gold.db"

    @property
    def manifest(self) -> Path:
        return self.directory / "ufo_gold.manifest.json"

    @property
    def silver_readiness(self) -> Path:
        return self.directory / "silver.readiness.json"

    @property
    def verification(self) -> Path:
        return self.directory / "ufo_gold.verification.json"

    @property
    def readiness(self) -> Path:
        return self.directory / "ufo_gold.readiness.json"

    @property
    def serving(self) -> Path:
        return self.directory / "serving" / "ufo_gold_serving.db"

    @property
    def serving_manifest(self) -> Path:
        return self.directory / "serving" / "ufo_gold_serving.manifest.json"

    @property
    def certified(self) -> Path:
        return self.directory / "certified_queries.json"

    @property
    def evals_spec(self) -> Path:
        return self.directory / "GOLD_EVALS.json"

    @property
    def evals_dir(self) -> Path:
        return self.directory / "evals"

    @property
    def docs(self) -> Path:
        return self.directory / "docs"

    @property
    def release(self) -> Path:
        return self.directory / "release.json"

    @property
    def metrics(self) -> Path:
        return self.directory / "build.metrics.json"

    @staticmethod
    def of_serving(serving: Path) -> "GoldLayout | None":
        """Layout that contains this serving cache, if it sits in one."""
        serving = Path(serving).resolve()
        if serving.name == "ufo_gold_serving.db" and serving.parent.name == "serving":
            return GoldLayout(serving.parent.parent)
        return None


LAYOUTS = {"silver": SilverLayout, "gold": GoldLayout}


# -- build lock --------------------------------------------------------------
@contextmanager
def build_lock(data: Path):
    """Exclusive publication lock for one data directory; fails fast if held."""
    data = Path(data)
    data.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(data / LOCK, timeout=0, isolation_level=None)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS lock (id INTEGER PRIMARY KEY)")
        conn.execute("BEGIN EXCLUSIVE")
    except sqlite3.OperationalError as exc:
        conn.close()
        raise BuildLocked(f"Otro build está publicando en {data}. Espera a que termine; "
                          "si el proceso murió, el sistema ya liberó el bloqueo y basta con repetir.") from exc
    try:
        yield
    finally:
        try:
            conn.execute("ROLLBACK")
        finally:
            conn.close()


# -- catalog -----------------------------------------------------------------
def catalog_path(data: Path) -> Path:
    return Path(data) / CATALOG


@contextmanager
def catalog(data: Path):
    path = catalog_path(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        yield conn
    finally:
        conn.close()


def approved(data: Path, layer: str) -> dict | None:
    """Approved version of a layer, or None. Read-only: never creates the catalog."""
    path = catalog_path(data)
    if not path.exists():
        return None
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)) as conn:
        try:
            row = conn.execute("""SELECT v.version, v.directory, v.identity, v.release_sha256, v.parent_version, a.promoted_at
                                  FROM approved a JOIN version v ON v.layer=a.layer AND v.version=a.version
                                  WHERE a.layer=?""", (layer,)).fetchone()
        except sqlite3.OperationalError:
            return None
    if row is None:
        return None
    keys = ("version", "directory", "identity", "release_sha256", "parent_version", "promoted_at")
    item = dict(zip(keys, row))
    item["path"] = Path(data) / Path(*item["directory"].split("/"))
    return item


def versions(data: Path, layer: str) -> list[dict]:
    path = catalog_path(data)
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)) as conn:
        rows = conn.execute("""SELECT v.version, v.directory, v.identity, v.parent_version, p.promoted_at
                               FROM version v LEFT JOIN (SELECT layer, version, MAX(promoted_at) promoted_at FROM promotion GROUP BY 1, 2) p
                               ON p.layer=v.layer AND p.version=v.version WHERE v.layer=? ORDER BY v.registered_at, v.version""",
                            (layer,)).fetchall()
    return [dict(zip(("version", "directory", "identity", "parent_version", "promoted_at"), r)) for r in rows]


def layout(data: Path, layer: str):
    """Layout of the approved version of a layer, or None."""
    item = approved(data, layer)
    return LAYOUTS[layer](item["path"]) if item else None


# -- candidates and release manifests ---------------------------------------
def new_candidate(data: Path, layer: str, owner: str = "manual") -> Path:
    """Fresh, empty directory with a name no other build can produce.

    ``owner="pipeline"`` marks candidates of build_all.py: if one is left
    unpromoted by a failure, the next successful build removes it. Candidates
    created by hand with the individual CLIs are never removed automatically.
    """
    base = Path(data) / layer / "versions"
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = base / f"{stamp}-{os.getpid()}-{secrets.token_hex(4)}"
    path.mkdir()
    write_text(path / ".candidate", json.dumps({"owner": owner, "pid": os.getpid(), "created_at": now()}) + "\n")
    return path


def candidate_owner(path: Path) -> str | None:
    try:
        return json.loads((Path(path) / ".candidate").read_text(encoding="utf-8")).get("owner")
    except (OSError, ValueError, AttributeError):
        return None


def relative(data: Path, path: Path) -> str:
    return Path(path).resolve().relative_to(Path(data).resolve()).as_posix()


def tracked_files(directory: Path) -> dict:
    """Every file of a version with its SHA-256 and size (memoised hashes)."""
    directory = Path(directory)
    files = {}
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        name = path.relative_to(directory).as_posix()
        if name in UNTRACKED or name.endswith((".building", "-journal", "-wal", "-shm")):
            continue
        files[name] = {"sha256": digest(path), "size_bytes": path.stat().st_size}
    return files


def write_release(directory: Path, layer: str, identity: str, **extra) -> dict:
    release = {"layer": layer, "version": Path(directory).name, "identity": identity,
               "written_at": now(), **extra, "files": tracked_files(directory)}
    write_text(Path(directory) / "release.json", json.dumps(release, ensure_ascii=False, indent=2) + "\n")
    return release


def check_release(directory: Path, expected_sha: str | None = None, files=None) -> dict:
    """Load release.json and verify it (and the named files) against the promotion."""
    path = Path(directory) / "release.json"
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReleaseError(f"Falta o es ilegible {path}") from exc
    if expected_sha is not None and digest(path) != expected_sha:
        raise ReleaseError(f"{path} no es el manifiesto que se promovió (modificado o sustituido)")
    entries = release.get("files") or {}
    for name in files if files is not None else entries:
        entry = entries.get(name)
        target = Path(directory) / Path(*name.split("/"))
        if entry is None:
            raise ReleaseError(f"La versión {Path(directory).name} no registra {name}")
        if not target.is_file() or target.stat().st_size != entry["size_bytes"] or digest(target) != entry["sha256"]:
            raise ReleaseError(f"{target} no coincide con su versión publicada")
    return release


def promote(data: Path, layer: str, directory: Path, identity: str, parent_version: str | None = None) -> dict:
    """Make a verified candidate the approved version, in one transaction."""
    if layer not in LAYERS:
        raise ValueError(layer)
    directory = Path(directory)
    release_sha = digest(directory / "release.json")
    stamp = now()
    with catalog(data) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT version FROM approved WHERE layer=?", (layer,)).fetchone()
            conn.execute("INSERT INTO version VALUES (?,?,?,?,?,?,?)",
                         (layer, directory.name, relative(data, directory), identity, release_sha, parent_version, stamp))
            conn.execute("""INSERT INTO approved (layer, version, promoted_at) VALUES (?,?,?)
                            ON CONFLICT(layer) DO UPDATE SET version=excluded.version, promoted_at=excluded.promoted_at""",
                         (layer, directory.name, stamp))
            conn.execute("INSERT INTO promotion (layer, version, previous_version, promoted_at) VALUES (?,?,?,?)",
                         (layer, directory.name, row[0] if row else None, stamp))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return {"layer": layer, "version": directory.name, "previous_version": row[0] if row else None, "promoted_at": stamp}


# -- readers -----------------------------------------------------------------
def open_approved_gold(data: Path) -> tuple[GoldLayout, dict]:
    """Approved Gold load, verified as one complete promoted set.

    Checks catalog → release.json → readiness (ready_for_agent for this load)
    → serving manifest and certified queries of that same load.
    """
    item = approved(data, "gold")
    if item is None:
        raise ReleaseError(f"No hay una carga Gold aprobada en {catalog_path(data)}. "
                           "Ejecuta `python scripts/build_all.py` (o `--desde gold`).")
    gold = GoldLayout(item["path"])
    release = check_release(gold.directory, item["release_sha256"],
                            files=["ufo_gold.readiness.json", "serving/ufo_gold_serving.manifest.json",
                                   "serving/ufo_gold_serving.db", "certified_queries.json"])
    load_id = item["identity"]
    readiness = json.loads(gold.readiness.read_text(encoding="utf-8"))
    serving = json.loads(gold.serving_manifest.read_text(encoding="utf-8"))
    if release.get("identity") != load_id or readiness.get("load_id") != load_id or readiness.get("ready_for_agent") is not True:
        raise ReleaseError(f"La versión {item['version']} no está aprobada para la carga {load_id}")
    if serving.get("load_id") != load_id:
        raise ReleaseError(f"La caché de la versión {item['version']} pertenece a otra carga")
    return gold, {"source": "catalog", "version": item["version"], "load_id": load_id, "promoted_at": item["promoted_at"],
                  "readiness_load_id": readiness["load_id"], "serving_load_id": serving["load_id"],
                  "silver_version": item["parent_version"]}


def default_silver(data: Path) -> Path:
    """Database for Silver CLIs: the approved version, else the legacy path."""
    current = layout(data, "silver")
    return current.database if current else Path(data) / "silver" / "ufo.db"


# -- cleanup -----------------------------------------------------------------
def _remove_tree(path: Path) -> bool:
    """Delete a version directory; False if a file is still open (Windows)."""
    for item in Path(path).rglob("*"):
        try:
            os.chmod(item, stat.S_IWUSR | stat.S_IRUSR | (stat.S_IXUSR if item.is_dir() else 0))
        except OSError:
            pass
    try:
        shutil.rmtree(path)
        return True
    except OSError:
        return False


def prune(data: Path, keep: int = 2, protect=()) -> list[str]:
    """Remove orphan pipeline candidates and versions older than the last ``keep`` promoted.

    Call it only while holding the build lock. The current version, the
    previous one and the Silver version each kept Gold load came from stay.
    """
    removed = []
    protect = {Path(p).resolve() for p in protect}
    kept_silver = set()
    for layer in ("gold", "silver"):
        base = Path(data) / layer / "versions"
        if not base.is_dir():
            continue
        registered = versions(data, layer)
        current = approved(data, layer)
        promoted = [v for v in registered if v["promoted_at"]]
        promoted.sort(key=lambda v: v["promoted_at"])
        keep_names = {v["version"] for v in promoted[-keep:]}
        if current:
            keep_names.add(current["version"])
        if layer == "gold":
            kept_silver = {v["parent_version"] for v in registered if v["version"] in keep_names and v["parent_version"]}
        else:
            keep_names |= kept_silver
        names = {v["version"] for v in registered}
        for path in sorted(base.iterdir()):
            if not path.is_dir() or path.resolve() in protect or path.name in keep_names:
                continue
            if path.name not in names and candidate_owner(path) != "pipeline":
                continue        # manual candidate: left to its owner
            name = relative(data, path)
            if _remove_tree(path):
                removed.append(name)
    return removed
