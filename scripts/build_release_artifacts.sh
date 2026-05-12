#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DIST="$ROOT/dist"
TMP="${TMPDIR:-/tmp}/agentcapsule-build-release"
VENV="$TMP/venv"

rm -rf "$DIST"
mkdir -p "$DIST"
rm -rf "$TMP"
mkdir -p "$TMP"

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip build
"$VENV/bin/python" -m build --sdist --wheel --outdir "$DIST" "$ROOT"

(
  cd "$DIST"
  sha256sum ./* > SHA256SUMS.txt
)

echo "Release artifacts written to: $DIST"
