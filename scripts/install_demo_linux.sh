#!/usr/bin/env bash
set -euo pipefail
launcher=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/run_demo.py

# Debian/Ubuntu. Node is installed for the current user.
case "$(uname -m)" in
    x86_64) platform=linux-x64 ;;
    aarch64) platform=linux-arm64 ;;
    *) echo "Arquitectura de Linux no compatible." >&2; exit 1 ;;
esac

if ! command -v apt-get >/dev/null; then
    echo "Este instalador requiere Debian o Ubuntu con apt." >&2
    exit 1
fi

echo '[Requisitos] Actualizando el indice de paquetes de apt...'
sudo apt-get update
echo '[Requisitos] Instalando Python, venv y herramientas de descarga...'
sudo apt-get install -y python3 python3-venv curl ca-certificates xz-utils
python3 -c 'import sqlite3, sys; sys.exit(0 if sys.version_info >= (3, 11) else "Se requiere Python 3.11 o superior.")'

work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
cd "$work"
release=https://nodejs.org/download/release/latest-v22.x
echo '[Requisitos] Buscando la version de Node.js 22...'
curl -fsSLO "$release/SHASUMS256.txt"
archive=$(awk -v platform="$platform" '$2 ~ ("^node-v22[.][0-9.]+-" platform "[.]tar[.]xz$") {print $2}' SHASUMS256.txt)
[[ "$archive" =~ ^node-v22\.[0-9]+\.[0-9]+-linux-(x64|arm64)\.tar\.xz$ ]]
echo "[Requisitos] Descargando $archive..."
curl -fSLO "$release/$archive"
echo '[Requisitos] Verificando el SHA-256 de Node.js...'
awk -v name="$archive" '$2 == name {print}' SHASUMS256.txt | sha256sum --check --strict -
echo '[Requisitos] Instalando Node.js 22 y npm para el usuario actual...'
mkdir -p "$HOME/.local"
tar -xJf "$archive" -C "$HOME/.local"

export PATH="$HOME/.local/${archive%.tar.xz}/bin:$PATH"
cd -- "$(dirname -- "$launcher")/.."
echo '[Requisitos] Instalacion completa. Iniciando el lanzador de la muestra...'
python3 "$launcher" "$@"
