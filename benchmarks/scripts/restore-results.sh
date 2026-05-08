#!/usr/bin/env bash
# restore-results.sh — download a benchmark artifact from a GitHub Release
# and extract it back to its source path under benchmarks/results/.
#
# Usage:
#   restore-results.sh <release-tag> [options]
#
# Example:
#   restore-results.sh bench-rq2a-20260507-sonnet4
#   # → benchmarks/results/rq2a/speca_sonnet4/ populated
#
# Options:
#   --repo <owner/name>  GH repo. Default: auto-detected by `gh`.
#   --out  <dir>         Override the parent directory we extract into.
#                        By default we use the manifest's recorded
#                        `source_path` (i.e. restore in place).
#   --force              Remove an existing target tree before extracting.
#   --keep-archive       Copy the downloaded .tar.zst + manifest beside the
#                        extracted tree (useful for re-uploads).
#   -h, --help           Show this help.
#
# Verifies the downloaded tarball's sha256 against the manifest, and the
# extracted tree's file count against the manifest.
# --- end help ---

set -euo pipefail
err() { echo "restore-results.sh: $*" >&2; exit 1; }
log() { echo "restore-results.sh: $*"; }

usage() {
  awk '/^# --- end help ---/{exit} /^# /{sub(/^# ?/,""); print}' "$0"
  exit "${1:-2}"
}

TAG=""
REPO=""
OUT_OVERRIDE=""
KEEP_ARCHIVE=0
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)      usage 0 ;;
    --repo)         REPO="${2:-}"; shift 2 ;;
    --out)          OUT_OVERRIDE="${2:-}"; shift 2 ;;
    --keep-archive) KEEP_ARCHIVE=1; shift ;;
    --force)        FORCE=1; shift ;;
    --)             shift; break ;;
    -*)             err "unknown flag: $1" ;;
    *)
      [ -z "$TAG" ] || err "extra positional argument: $1"
      TAG="$1"; shift ;;
  esac
done

[ -n "$TAG" ] || usage 2

case "$TAG" in
  bench-*) ;;
  *) err "unexpected tag prefix (expected 'bench-*'): $TAG" ;;
esac

for tool in gh tar jq zstd python3; do
  command -v "$tool" >/dev/null 2>&1 || err "$tool not found in PATH"
done
TAR_HELP="$(tar --help 2>/dev/null || true)"
if ! grep -q -- '--zstd' <<<"$TAR_HELP"; then
  err "tar lacks --zstd support. On Linux: install GNU tar 1.31+. On macOS: \`brew install gnu-tar\` and use \`gtar\`, or upgrade to libarchive bsdtar 3.5+."
fi
unset TAR_HELP

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    python3 - "$1" <<'PY'
import hashlib, sys
h = hashlib.sha256()
with open(sys.argv[1], 'rb') as f:
    for chunk in iter(lambda: f.read(1 << 20), b''):
        h.update(chunk)
print(h.hexdigest())
PY
  fi
}

WORK="$(mktemp -d -t restore-results.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

GH_FLAGS=()
[ -n "$REPO" ] && GH_FLAGS+=(--repo "$REPO")

log "downloading release $TAG to $WORK"
gh release download "$TAG" \
   "${GH_FLAGS[@]}" \
   --pattern "${TAG}.tar.zst" \
   --pattern "${TAG}.manifest.json" \
   --dir "$WORK"

TAR="$WORK/${TAG}.tar.zst"
MANIFEST="$WORK/${TAG}.manifest.json"
[ -f "$TAR" ]      || err "downloaded tarball missing: $TAR"
[ -f "$MANIFEST" ] || err "manifest missing: $MANIFEST"

SRC_PATH="$(jq -r '.source_path'      "$MANIFEST")"
ARCHIVE_ROOT="$(jq -r '.archive_root' "$MANIFEST")"
N_EXPECTED="$(jq -r '.n_files'        "$MANIFEST")"
SHA_EXPECTED="$(jq -r '.archive_sha256 // ""' "$MANIFEST")"

[ -n "$SRC_PATH" ]     && [ "$SRC_PATH" != "null" ]     || err "manifest missing source_path"
[ -n "$ARCHIVE_ROOT" ] && [ "$ARCHIVE_ROOT" != "null" ] || err "manifest missing archive_root"
[ -n "$N_EXPECTED" ]   && [ "$N_EXPECTED" != "null" ]   || err "manifest missing n_files"

case "$ARCHIVE_ROOT" in
  *..*|/*) err "manifest archive_root looks unsafe: '$ARCHIVE_ROOT'" ;;
esac
case "$SRC_PATH" in
  /*|*..*) err "manifest source_path looks unsafe: '$SRC_PATH' (must be relative, no '..')" ;;
esac

# ---- verify sha256 BEFORE extracting -------------------------------------
if [ -n "$SHA_EXPECTED" ]; then
  SHA_ACTUAL="$(sha256_file "$TAR")"
  if [ "$SHA_ACTUAL" != "$SHA_EXPECTED" ]; then
    err "sha256 mismatch: downloaded $SHA_ACTUAL, manifest $SHA_EXPECTED"
  fi
  log "sha256 verified: $SHA_ACTUAL"
else
  log "manifest has no archive_sha256 (older artifact?); skipping checksum"
fi

if [ -n "$OUT_OVERRIDE" ]; then
  EXTRACT_PARENT="$OUT_OVERRIDE"
else
  EXTRACT_PARENT="$(dirname "$SRC_PATH")"
fi
mkdir -p "$EXTRACT_PARENT"

TARGET="$EXTRACT_PARENT/$ARCHIVE_ROOT"
if [ -e "$TARGET" ]; then
  if [ "$FORCE" = 1 ]; then
    log "removing existing $TARGET (--force)"
    rm -rf -- "$TARGET"
  else
    err "$TARGET already exists; pass --force to replace it, or --out <dir> to extract elsewhere"
  fi
fi

log "extracting to $TARGET"
tar --zstd -xf "$TAR" -C "$EXTRACT_PARENT"

N_ACTUAL="$(python3 - "$TARGET" <<'PY'
import os, sys
n = 0
for _, _, fs in os.walk(sys.argv[1]):
    n += len(fs)
print(n)
PY
)"

if [ "$N_ACTUAL" != "$N_EXPECTED" ]; then
  err "file count mismatch: extracted $N_ACTUAL, manifest says $N_EXPECTED"
fi
log "verified: $N_ACTUAL files extracted"

if [ "$KEEP_ARCHIVE" = 1 ]; then
  cp "$TAR"      "$EXTRACT_PARENT/${TAG}.tar.zst"
  cp "$MANIFEST" "$EXTRACT_PARENT/${TAG}.manifest.json"
  log "kept archive copies in $EXTRACT_PARENT/"
fi

log "done"
