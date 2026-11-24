"""Ejecuta un fragmento original del generador de láminas de DB Test."""
import argparse
import collections
import datetime
import json
import math
import re
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

BIBLIOTECA = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("propuesta", help="Carpeta de la propuesta")
    parser.add_argument("salida", type=Path, help="Directorio existente para SVG y PNG")
    parser.add_argument("--origen", type=Path, default=BIBLIOTECA.parent / "DB Test")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.propuesta):
        parser.error("Indica el nombre de una carpeta de la biblioteca.")
    fragmento = next((BIBLIOTECA / estado / args.propuesta / "reproduccion" / "fuente-estatica.py"
                      for estado in ("done", "pendientes")
                      if (BIBLIOTECA / estado / args.propuesta / "reproduccion" / "fuente-estatica.py").is_file()),
                     BIBLIOTECA / "pendientes" / args.propuesta / "reproduccion" / "fuente-estatica.py")
    if not fragmento.is_file():
        parser.error("No hay generador Python para esta propuesta. Usa reproducir.cjs o la lámina recuperada.")
    if not args.salida.is_dir():
        parser.error("El directorio de salida debe existir.")

    source = args.origen.resolve()
    data = json.loads((source / "sketchbook-v2/data.json").read_text())
    ca, ml, st = (data[key] for key in ("ca", "ml", "st"))
    environment = {
        "ROOT": source, "OUT": args.salida.resolve(), "np": np, "plt": plt,
        "json": json, "math": math, "datetime": datetime, "re": re, "collections": collections,
        "LinearSegmentedColormap": LinearSegmentedColormap, "ca": ca, "ml": ml, "st": st,
        "n": len(ca), "meta": [],
        # El original de D17 lee la intersección con duración y testigos ya guardada en el snapshot.
        "rows": data["km"]["rows"] if args.propuesta == "duracion-testigos" else [],
    }
    common = Path(__file__).with_name("estilos-exportacion.py")
    for code in (common, fragmento):
        exec(compile(code.read_text(), str(code), "exec"), environment)
    for entry in environment["meta"]:
        print(args.salida / entry["file"])


if __name__ == "__main__":
    main()
