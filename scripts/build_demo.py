"""Build the synthetic Gold sample used by the local application guide."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from gold_fixture import serving_fixture


def show_progress(message: str) -> None:
    print(f"[Datos] {message}", flush=True)


def main() -> None:
    output = ROOT / "data" / "demo"
    try:
        output.mkdir(parents=True)
    except FileExistsError:
        raise SystemExit("data/demo ya existe. Reutiliza la muestra o mueve esa carpeta antes de generarla de nuevo.") from None

    analytics, _, _ = serving_fixture(output, progress=show_progress)
    analytics.run_certified("CQ_TEST_SOURCES")
    print(f"Muestra Gold lista en {output} (carga {analytics.load_id}).")


if __name__ == "__main__":
    main()
