"""Install, start and verify the local application with synthetic Gold data."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener
import venv


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
ENVIRONMENT = ROOT / "apps" / "api" / ".venv"
EXAMPLE = "/api/agent/certified/CQ_TEST_SOURCES"


def verify(server: subprocess.Popen, api: str, web: str) -> None:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"Los servicios terminaron con código {server.returncode}.")
        try:
            with opener.open(api + "/api/health", timeout=2) as response:
                health = json.load(response)
            with opener.open(web + EXAMPLE, timeout=2) as response:
                example = json.load(response)
            if (health.get("status") == "ok" and example.get("result_type") == "certified"
                    and example.get("rows") and health.get("gold_load_id")
                    == example.get("provenance", {}).get("gold_load_id")):
                return
            raise RuntimeError("La API y el ejemplo no devuelven la misma carga Gold con resultados.")
        except OSError as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"No se pudo verificar la muestra: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verifica el arranque y detén los servicios.")
    args = parser.parse_args()
    windows = os.name == "nt"
    npm = shutil.which("npm.cmd" if windows else "npm")
    node = shutil.which("node")
    if sys.version_info < (3, 11) or not npm or not node:
        parser.exit(1, "Instala Python 3.11+ y Node.js 20.9+ con npm antes de continuar.\n")
    python = ENVIRONMENT / ("Scripts/python.exe" if windows else "bin/python")
    serving = DEMO / "serving" / "ufo_gold_serving.db"
    certified = DEMO / "certified_queries.json"
    web = "http://127.0.0.1:" + os.environ.get("AGENT_DEV_WEB_PORT", "3000")
    api = "http://127.0.0.1:" + os.environ.get("AGENT_DEV_API_PORT", "8000")
    server = None
    try:
        if not python.is_file():
            venv.create(ENVIRONMENT, with_pip=True)
        subprocess.run([python, "-m", "pip", "install", "-e", "apps/api"], cwd=ROOT, check=True)
        subprocess.run([npm, "--prefix", "apps/web", "ci"], cwd=ROOT, check=True)
        if not DEMO.exists():
            subprocess.run([python, "-X", "utf8", "scripts/build_demo.py"], cwd=ROOT, check=True)
        if not all(path.is_file() for path in (serving, serving.with_suffix(".manifest.json"), certified)):
            raise RuntimeError("La muestra está incompleta. Mueve data/demo y vuelve a ejecutar el lanzador.")
        env = dict(os.environ, AGENT_GOLD_SERVING=str(serving), AGENT_CERTIFIED_QUERIES=str(certified),
                   AGENT_DEV_STOP_ON_EOF="1")
        server = subprocess.Popen([node, "apps/web/scripts/dev.mjs"], cwd=ROOT, env=env, stdin=subprocess.PIPE)
        verify(server, api, web)
        print(f"API y ejemplo verificados. Abre {web}/agent#consultas-de-ejemplo y elige «Informes por fuente».", flush=True)
        return 0 if args.check else server.wait()
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"No se pudo iniciar la muestra: {exc}", file=sys.stderr)
        return 1
    finally:
        if server is not None and server.poll() is None:
            server.stdin.close()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.terminate()
                server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
