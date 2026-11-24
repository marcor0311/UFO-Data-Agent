#!/usr/bin/env python3
"""Build the whole data pipeline with one command: Bronze → Silver → Gold.

    python3 scripts/build_all.py                    # macOS / Linux
    py -3.12 scripts\\build_all.py                   # Windows (PowerShell)

Phases, in order, stopping at the first failure:

  bronze  download (or reuse the local copy, offline) and validate the pinned snapshot
  silver  rebuild Silver in a new version directory; custody, acceptance and review;
          promote the Silver/report pair
  gold    custody and acceptance of the approved Silver; Gold model, serving cache,
          certified queries, independent verification, evaluations and
          ready_for_agent, all inside a new candidate directory; promote the load

Each layer is published by one transaction on <datos>/releases.sqlite3 after
every control has passed. Until then the previously approved version stays
current, also if the process fails or is interrupted. Only one build publishes
at a time (lock <datos>/.build.lock). Everything runs in this process with a
shared context: each stable file is hashed once and each exact Silver is
accepted once. A new invocation verifies again everything it reuses.

The versioned references (config/gold/certified_queries.json, docs/GOLD_EVALS.json
and docs/GOLD_CATALOG.*) are never rewritten by a build; the results of each
load stay in its version. Update them explicitly with --actualizar-referencias.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CANDIDATES = ("python3.14", "python3.13", "python3.12", "python3.11")
PHASES = ("bronze", "silver", "gold")
REFERENCES = {"certified_queries.json": "config/gold/certified_queries.json", "GOLD_EVALS.json": "docs/GOLD_EVALS.json",
              "docs/GOLD_CATALOG.json": "docs/GOLD_CATALOG.json", "docs/GOLD_CATALOG.md": "docs/GOLD_CATALOG.md",
              "docs/GOLD_ENTITIES.json": "docs/GOLD_ENTITIES.json"}
EXIT_FAILED, EXIT_LOCKED = 1, 3


def ensure_modern_python() -> None:
    if sys.version_info >= (3, 11):
        return
    if os.name == "nt":
        raise SystemExit("ERROR: se requiere Python 3.11+. Ejecuta: py -3.12 scripts\\build_all.py")
    for name in CANDIDATES:
        found = shutil.which(name)
        if found:
            print(f"Python {sys.version.split()[0]} es antiguo; se usa {found}", flush=True)
            os.execv(found, [found, __file__, *sys.argv[1:]])
    raise SystemExit("ERROR: se requiere Python 3.11+. Instálalo con: brew install python@3.14")


ensure_modern_python()
sys.path.insert(0, str(SCRIPTS))

import build_bronze  # noqa: E402
import build_gold  # noqa: E402
import build_silver  # noqa: E402
import check_gold_ready  # noqa: E402
import discover_gold  # noqa: E402
from gold_common import load_json, silver_provenance  # noqa: E402
import gold_query  # noqa: E402
import pipeline_context  # noqa: E402
from pipeline_context import write_text  # noqa: E402
import releases  # noqa: E402
from releases import GoldLayout, SilverLayout  # noqa: E402
import review_silver  # noqa: E402
import run_gold_evals  # noqa: E402
import verify_gold_independent  # noqa: E402


class PipelineError(RuntimeError):
    def __init__(self, phase: str, message: str, resume: str | None = None):
        super().__init__(message)
        self.phase = phase
        self.resume = resume or phase


def gib(n: int | float) -> str:
    return f"{n / 1024 ** 3:.2f} GiB"


def folder_size(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file()) if Path(path).exists() else 0


# -- phases -----------------------------------------------------------------
def bronze_phase(ctx, data: Path, manifest_path: Path, source: str | None) -> Path:
    path = releases.bronze_path(data)
    manifest = load_json(manifest_path)
    with ctx.phase("bronze.validación"):
        try:
            build_bronze.download(path, manifest, source)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            raise PipelineError("bronze", f"No se pudo obtener Bronze: {exc}") from exc
        report = build_bronze.validate(path, manifest)
        write_text(path.with_suffix(".validation.json"), json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if not report["passed"]:
        failed = [name for name, check in report["checks"].items() if not check["passed"]]
        raise PipelineError("bronze", f"Bronze no pasó la validación: {', '.join(failed)}")
    return path


def silver_phase(ctx, data: Path, manifest_path: Path, before_promote=None, out=print) -> dict:
    bronze = releases.bronze_path(data)
    manifest = load_json(manifest_path)
    policy = load_json(build_silver.POLICY)
    candidate = SilverLayout(releases.new_candidate(data, "silver", owner="pipeline"))
    out(f"    candidato Silver: {releases.relative(data, candidate.directory)}", flush=True)
    with ctx.phase("silver.construcción"):
        try:
            build_silver.build(bronze, candidate.database, manifest, policy)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise PipelineError("silver", f"Silver no se construyó: {exc}") from exc
    with ctx.phase("silver.custodia"):
        custody = silver_provenance(candidate.database, bronze, manifest_path)
        if not custody["passed"]:
            raise PipelineError("silver", "Silver no supera la cadena de custodia: " + "; ".join(custody["problems"]))
    with ctx.phase("silver.aceptación"):
        try:
            readiness = build_gold.silver_gate(candidate.database, bronze, candidate.readiness)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise PipelineError("silver", f"NO APTA PARA GOLD: {exc}") from exc
        if not readiness.get("ready_for_gold") or readiness.get("silver_sha256") != custody["silver_sha256"]:
            raise PipelineError("silver", "La puerta de aceptación no aprobó este Silver exacto")
    with ctx.phase("silver.revisión"):
        try:
            review = review_silver.review(bronze, candidate.database, policy)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise PipelineError("silver", f"La revisión de Silver falló: {exc}") from exc
        write_text(candidate.review, json.dumps(review, ensure_ascii=False, indent=2) + "\n")
    releases.write_release(candidate.directory, "silver", custody["silver_sha256"], run_id=custody["silver_run_id"],
                           bronze_sha256=custody["bronze_sha256"])
    if before_promote:
        before_promote("silver", candidate)
    with ctx.phase("silver.promoción"):
        promoted = releases.promote(data, "silver", candidate.directory, custody["silver_sha256"])
    return {"version": promoted["version"], "previous": promoted["previous_version"], "sha256": custody["silver_sha256"]}


def gold_phase(ctx, data: Path, root: Path, manifest_path: Path, certified_source: Path, evals_source: Path,
               before_promote=None, out=print) -> dict:
    current = releases.approved(data, "silver")
    if current is None:
        raise PipelineError("gold", f"No hay una Silver aprobada en {releases.catalog_path(data)}. "
                                    "Ejecuta `build_all.py --desde silver`.", resume="silver")
    silver = SilverLayout(current["path"])
    bronze = releases.bronze_path(data)
    out(f"    Silver aprobada: {current['version']} ({current['identity'][:12]})", flush=True)
    with ctx.phase("gold.custodia_silver"):
        try:
            releases.check_release(silver.directory, current["release_sha256"], files=["ufo.db", "ufo.validation.json"])
        except releases.ReleaseError as exc:
            raise PipelineError("gold", f"La Silver aprobada no coincide con su publicación: {exc}. "
                                        "Ejecuta `build_all.py --desde silver`.", resume="silver") from exc
        custody = silver_provenance(silver.database, bronze, manifest_path)
        if not custody["passed"]:
            raise PipelineError("gold", "Silver no es apta para Gold: " + "; ".join(custody["problems"])
                                + ". Ejecuta `build_all.py --desde silver`.", resume="silver")
    with ctx.phase("gold.aceptación_silver"):
        try:
            readiness = build_gold.silver_gate(silver.database, bronze)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise PipelineError("gold", f"La Silver aprobada no pasa su aceptación: {exc}") from exc
        if not readiness.get("ready_for_gold") or readiness.get("silver_sha256") != custody["silver_sha256"]:
            raise PipelineError("gold", "La puerta de Silver no aprobó la Silver aprobada exacta")
    candidate = GoldLayout(releases.new_candidate(data, "gold", owner="pipeline"))
    out(f"    candidato Gold: {releases.relative(data, candidate.directory)}", flush=True)
    try:
        with ctx.phase("gold.modelo"):
            manifest = build_gold.build(root, silver_path=silver.database, bronze_path=bronze, output=candidate.database,
                                        readiness_path=candidate.silver_readiness, data=data, bronze_manifest=manifest_path)
        load_id = manifest["load_id"]
        with ctx.phase("gold.serving"):
            discover_gold.discover(root, gold=candidate.database)
        with ctx.phase("gold.certificación"):
            write_text(candidate.certified, Path(certified_source).read_text(encoding="utf-8"))
            analytics = gold_query.Analytics(root, serving=candidate.serving, certified_path=candidate.certified)
            gold_query.certify(analytics=analytics)
        with ctx.phase("gold.verificación_independiente"):
            verification = verify_gold_independent.verify(
                root, write_references=True, gold=candidate.database, silver=silver.database, certified=candidate.certified,
                evals=evals_source, references_out=candidate.evals_spec, output=candidate.verification,
                hasher=ctx.digest, data=data)
            if not verification["passed"]:
                raise PipelineError("gold", "Verificación independiente rechazada: "
                                    + "; ".join(f"{c['check']} → {c['detail']}" for c in verification["failed"][:10]))
        with ctx.phase("gold.evaluaciones"):
            analytics = gold_query.Analytics(root, serving=candidate.serving, certified_path=candidate.certified)
            previous = releases.layout(data, "gold")
            evals = run_gold_evals.run(root, analytics=analytics, evals_path=candidate.evals_spec, folder=candidate.evals_dir,
                                       previous=[previous.evals_dir] if previous else [])
            if not evals["passed"]:
                failed = [r["id"] for r in evals["results"] if not r["passed"]]
                raise PipelineError("gold", f"Evaluaciones Gold fallidas: {failed[:20]}; referencias de la carga: "
                                            f"{evals['summary']['references_for_current_load']}")
        with ctx.phase("gold.ready_for_agent"):
            gate = check_gold_ready.full_gate(root, layout=candidate, silver_path=silver.database, bronze_path=bronze,
                                              bronze_manifest=manifest_path, data=data)
            write_text(candidate.readiness, json.dumps(gate, ensure_ascii=False, indent=2) + "\n")
            if not gate["ready_for_agent"] or gate["load_id"] != load_id:
                raise PipelineError("gold", f"GOLD NO APTA PARA EL AGENTE: {len(gate['failed'])} de {gate['checks']} controles "
                                            "fallaron: " + "; ".join(c["check"] for c in gate["failed"][:10]))
    except (OSError, ValueError, KeyError, sqlite3.Error, build_gold.GoldBuildError, gold_query.GoldUnavailable,
            gold_query.QueryError) as exc:
        raise PipelineError("gold", f"{type(exc).__name__}: {exc}") from exc
    releases.write_release(candidate.directory, "gold", load_id, silver_version=current["version"],
                           silver_sha256=custody["silver_sha256"], bronze_sha256=custody["bronze_sha256"],
                           ready_for_agent=True)
    if before_promote:
        before_promote("gold", candidate)
    with ctx.phase("gold.promoción"):
        promoted = releases.promote(data, "gold", candidate.directory, load_id, parent_version=current["version"])
    return {"version": promoted["version"], "previous": promoted["previous_version"], "load_id": load_id,
            "checks": gate["checks"], "directory": candidate.directory}


# -- space ------------------------------------------------------------------
def space_plan(data: Path, manifest_path: Path, wanted: set) -> dict:
    """Free space a run needs, from the sizes of the approved versions (or estimates)."""
    bronze_size = load_json(manifest_path)["size_bytes"]
    silver = releases.layout(data, "silver")
    gold = releases.layout(data, "gold")
    silver_size = silver.database.stat().st_size if silver and silver.database.exists() else int(1.4 * bronze_size)
    gold_size = folder_size(gold.directory) if gold else int(0.9 * silver_size)
    needed, basis = 0, []
    if "bronze" in wanted and not releases.bronze_path(data).exists():
        needed += bronze_size
        basis.append(f"Bronze {gib(bronze_size)}")
    if "silver" in wanted:
        needed += int(silver_size * 1.1)
        basis.append(f"Silver ~{gib(silver_size)}" + ("" if silver else " (estimado)"))
    if "gold" in wanted:
        needed += int(gold_size * 1.1)
        basis.append(f"Gold+serving ~{gib(gold_size)}" + ("" if gold else " (estimado)"))
    free = shutil.disk_usage(data).free
    return {"needed_bytes": needed, "free_bytes_before": free, "basis": basis}


# -- explicit operations ----------------------------------------------------
def _definitions_of_certified(doc: dict) -> dict:
    limits = load_json(ROOT / "config/gold/gold.json")["query"]
    out = {}
    for item in doc.get("queries", []):
        rest = {k: v for k, v in item.items() if k not in ("expected_result", "verification", "query_sha256", "query")}
        out[item["id"]] = {**rest, "query_sha256": gold_query.query_digest(item["query"], limits)}
    return out


def _definitions_of_evals(doc: dict) -> dict:
    return {**{k: v for k, v in doc.items() if k not in ("questions", "reference_load")},
            "questions": [{k: v for k, v in q.items() if k != "reference_answer"} for q in doc.get("questions", [])]}


def update_references(data: Path, root: Path = ROOT, out=print) -> int:
    """Copy the generated references of the approved load into config/ and docs/."""
    current = releases.approved(data, "gold")
    if current is None:
        out("No hay una carga Gold aprobada; no hay referencias que copiar.", file=sys.stderr)
        return EXIT_FAILED
    gold = GoldLayout(current["path"])
    releases.check_release(gold.directory, current["release_sha256"], files=list(REFERENCES))
    certified_now = load_json(root / REFERENCES["certified_queries.json"])
    evals_now = load_json(root / REFERENCES["GOLD_EVALS.json"])
    if _definitions_of_certified(certified_now) != _definitions_of_certified(load_json(gold.certified)) or \
            _definitions_of_evals(evals_now) != _definitions_of_evals(load_json(gold.evals_spec)):
        out("Se conservan las referencias: las consultas certificadas o las preguntas de evaluación cambiaron "
            "desde la carga aprobada. Reconstruye Gold (`--desde gold`) y repite.", file=sys.stderr)
        return EXIT_FAILED
    for name, target in REFERENCES.items():
        source = gold.directory / Path(*name.split("/"))
        text = source.read_text(encoding="utf-8")
        destination = root / target
        changed = not destination.exists() or destination.read_text(encoding="utf-8") != text
        if changed:
            write_text(destination, text)
        out(f"{'actualizado' if changed else 'sin cambios'}: {target}")
    out(f"Referencias versionadas = carga {current['identity']} (versión {current['version']}).")
    return 0


def status(data: Path, out=print) -> int:
    for layer in ("silver", "gold"):
        item = releases.approved(data, layer)
        if item is None:
            out(f"{layer}: sin versión aprobada")
        else:
            out(f"{layer}: {item['version']}  identidad {item['identity']}  promovida {item['promoted_at']}"
                + (f"  desde Silver {item['parent_version']}" if item["parent_version"] else ""))
    return 0


# -- command ----------------------------------------------------------------
def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--desde", choices=PHASES, default="bronze",
                   help="Fase desde la que reanudar; las anteriores se reutilizan tras verificarlas")
    p.add_argument("--solo", choices=PHASES, help="Ejecutar únicamente esta fase")
    p.add_argument("--datos", type=Path, help="Directorio de datos (por defecto UFO_DATA_DIR o ./data)")
    p.add_argument("--fuente-bronze", default=os.environ.get("BRONZE_SOURCE"),
                   help="Archivo o URL de Bronze si aún no está en <datos>/bronze/ufo.db (BRONZE_SOURCE)")
    p.add_argument("--conservar", type=int, default=2, help="Versiones promovidas a conservar por capa (por defecto 2)")
    p.add_argument("--actualizar-referencias", action="store_true",
                   help="Copiar certificaciones, evaluaciones y catálogo de la carga aprobada a config/ y docs/")
    p.add_argument("--estado", action="store_true", help="Mostrar las versiones aprobadas y salir")
    return p


def run(argv=None, *, root: Path = ROOT, bronze_manifest: Path | None = None, certified_source: Path | None = None,
        evals_source: Path | None = None, acceptance=None, before_promote=None, out=print) -> int:
    args = parser().parse_args(argv)
    data = Path(args.datos).resolve() if args.datos else releases.data_root(root)
    if args.estado:
        return status(data, out)
    manifest_path = Path(bronze_manifest or root / "config/bronze.json")
    certified_source = Path(certified_source or root / "config/gold/certified_queries.json")
    evals_source = Path(evals_source or root / "docs/GOLD_EVALS.json")
    ctx = pipeline_context.reset()
    ctx.acceptance_override = acceptance
    wanted = {args.solo} if args.solo else set(PHASES[PHASES.index(args.desde):])
    began = time.monotonic()
    outcome = {"phases": sorted(wanted, key=PHASES.index), "data": str(data)}
    code = 0
    try:
        with releases.build_lock(data):
            if args.actualizar_referencias:
                return update_references(data, root, out)
            space = outcome["space"] = space_plan(data, manifest_path, wanted)
            out(f"Datos: {data}\nEspacio libre {gib(space['free_bytes_before'])}; necesario ~{gib(space['needed_bytes'])} "
                f"({', '.join(space['basis']) or 'nada nuevo'})", flush=True)
            if space["free_bytes_before"] < space["needed_bytes"]:
                raise PipelineError(outcome["phases"][0], "Espacio en disco insuficiente; libera espacio o usa --datos en otro disco")
            if "bronze" in wanted:
                out("\n==> Bronze: descarga (o copia local) y validación", flush=True)
                bronze_phase(ctx, data, manifest_path, args.fuente_bronze)
            if "silver" in wanted:
                out("\n==> Silver: construcción, custodia, aceptación, revisión y promoción", flush=True)
                outcome["silver"] = silver_phase(ctx, data, manifest_path, before_promote, out)
                out(f"    Silver promovida: {outcome['silver']['version']}", flush=True)
            if "gold" in wanted:
                out("\n==> Gold: modelo, caché, certificación, verificación, evaluaciones, ready_for_agent y promoción", flush=True)
                gold = gold_phase(ctx, data, root, manifest_path, certified_source, evals_source, before_promote, out)
                outcome["gold"] = {k: str(v) if isinstance(v, Path) else v for k, v in gold.items()}
                out(f"    Gold promovida: {gold['version']}; load_id {gold['load_id']}; {gold['checks']} controles", flush=True)
            removed = outcome["pruned"] = releases.prune(data, keep=max(1, args.conservar))
            if removed:
                out(f"Versiones retiradas: {len(removed)}", flush=True)
            outcome["status"] = "ok"
    except releases.BuildLocked as exc:
        out(f"\nPIPELINE NO INICIADO: {exc}", file=sys.stderr)
        return EXIT_LOCKED
    except (PipelineError, releases.ReleaseError) as exc:
        phase = getattr(exc, "phase", "?")
        outcome.update(status="failed", failed_phase=phase, error=str(exc))
        out(f"\nPIPELINE DETENIDO en “{phase}”: {exc}", file=sys.stderr)
        for layer in ("silver", "gold"):
            item = releases.approved(data, layer)
            out(f"  {layer} vigente: {item['version'] if item else 'ninguna'}", file=sys.stderr)
        resume = getattr(exc, "resume", None) if getattr(exc, "resume", None) in PHASES else "bronze"
        out(f"  Corrige la causa y repite con `build_all.py --desde {resume}`; "
            "el candidato fallido se conserva para diagnóstico y se retira en el próximo build correcto.", file=sys.stderr)
        code = EXIT_FAILED
    except KeyboardInterrupt:
        outcome["status"] = "interrupted"
        out("\nPIPELINE INTERRUMPIDO: las versiones aprobadas no cambiaron.", file=sys.stderr)
        code = 130
    finally:
        if "status" in outcome:
            if outcome.get("space"):
                outcome["space"]["free_bytes_after"] = shutil.disk_usage(data).free
            outcome["seconds"] = round(time.monotonic() - began, 1)
            outcome["metrics"] = ctx.summary()
            write_text(data / "build.metrics.json", json.dumps(outcome, ensure_ascii=False, indent=2) + "\n")
            if "gold" in outcome:
                write_text(GoldLayout(Path(outcome["gold"]["directory"])).metrics,
                           json.dumps(outcome, ensure_ascii=False, indent=2) + "\n")
    report(outcome, out)
    return code


def report(outcome: dict, out=print) -> None:
    metrics = outcome["metrics"]
    out("\nResumen por fase:")
    for entry in metrics["phases"]:
        out(f"  {entry['phase']:<32} {entry['seconds']:>8.1f} s  {entry['status']}")
    reads = metrics["hash_reads"]
    out(f"Lecturas completas de hash: {reads['count']} ({gib(reads['bytes'])}, {reads['seconds']:.1f} s); "
        f"archivos leídos más de una vez: {len(reads['repeated_files'])}")
    out(f"Aceptaciones completas de Silver: {metrics['silver_acceptance_runs']}")
    space = outcome.get("space") or {}
    if "free_bytes_after" in space:
        out(f"Espacio usado: {gib(space['free_bytes_before'] - space['free_bytes_after'])}")
    verdict = "completo" if outcome["status"] == "ok" else "detenido"
    out(f"Pipeline {verdict} en {outcome['seconds']:.0f} s. Métricas: {Path(outcome['data']) / 'build.metrics.json'}")


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
