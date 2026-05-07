#!/usr/bin/env bash
# publish-results.sh — bundle a benchmark results directory into a release
# artifact: <tag>.tar.zst plus a sidecar <tag>.manifest.json.
#
# Usage:
#   publish-results.sh <source-dir> <release-tag> [options]
#
# Example:
#   publish-results.sh \
#     benchmarks/results/rq2a/speca_sonnet4 \
#     bench-rq2a-20260507-sonnet4
#
# Options:
#   --out-dir <dir>   Where to write the tarball + manifest.
#                     Default: ./dist/bench-artifacts
#   --notes <text>    Free-form notes copied into the manifest.
#   --force           Overwrite an existing tarball.
#   -h, --help        Show this help.
#
# Outputs (in --out-dir):
#   <tag>.tar.zst       zstd-compressed tarball
#   <tag>.manifest.json provenance + size + file count + sha256
#
# The tarball preserves only the leaf directory name as its top-level entry
# (e.g. `speca_sonnet4/...`), and the manifest records the original
# `source_path` so `restore-results.sh` can rebuild the layout.
# --- end help ---

set -euo pipefail

err() { echo "publish-results.sh: $*" >&2; exit 1; }
log() { echo "publish-results.sh: $*"; }

usage() {
  awk '/^# --- end help ---/{exit} /^# /{sub(/^# ?/,""); print}' "$0"
  exit "${1:-2}"
}

SRC=""
TAG=""
OUT_DIR="./dist/bench-artifacts"
FORCE=0
NOTES_INPUT=""

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --out-dir) OUT_DIR="${2:-}"; [ -n "$OUT_DIR" ] || err "--out-dir requires a value"; shift 2 ;;
    --force)   FORCE=1; shift ;;
    --notes)   NOTES_INPUT="${2:-}"; shift 2 ;;
    --)        shift; break ;;
    -*)        err "unknown flag: $1" ;;
    *)
      if   [ -z "$SRC" ]; then SRC="$1"
      elif [ -z "$TAG" ]; then TAG="$1"
      else err "extra positional argument: $1"
      fi
      shift
      ;;
  esac
done

[ -n "$SRC" ] || usage 2
[ -n "$TAG" ] || usage 2
[ -d "$SRC" ] || err "source directory does not exist: $SRC"

case "$TAG" in
  bench-*) ;;
  *) err "refusing to publish: tag must start with 'bench-' (got '$TAG')" ;;
esac

# Tag → RQ extraction. Fail closed; do not silently record `unknown`.
RQ="$(printf '%s' "$TAG" | sed -nE 's/^bench-(rq[0-9a-z]+)-[0-9]{8}(-.*)?$/\1/p')"
[ -n "$RQ" ] || err "tag '$TAG' does not match bench-<rq>-<YYYYMMDD>[-<suffix>]"

# ---- locate the speca repo root from the script's own location ----------
# Avoid `git ... || cd ... && pwd` — the && binds tighter than expected and
# concatenates pwd onto the git output. Resolve in two steps.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$REPO_ROOT" ]; then
  REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"
fi
[ -d "$REPO_ROOT/benchmarks/results" ] \
  || err "could not locate <repo>/benchmarks/results from $SCRIPT_DIR (REPO_ROOT=$REPO_ROOT)"

# ---- portable realpath ---------------------------------------------------
realpath_p() {
  python3 - "$1" <<'PY'
import os, sys
print(os.path.realpath(sys.argv[1]))
PY
}

SRC_REAL="$(realpath_p "$SRC")"
RESULTS_REAL="$(realpath_p "$REPO_ROOT/benchmarks/results")"
case "$SRC_REAL" in
  "$RESULTS_REAL"/*) ;;
  *) err "refusing to publish: $SRC (resolved: $SRC_REAL) is not under $RESULTS_REAL" ;;
esac

SRC="${SRC%/}"
PARENT="$(dirname "$SRC_REAL")"
LEAF="$(basename "$SRC_REAL")"
[ "$LEAF" != "." ] && [ "$LEAF" != ".." ] || err "invalid source leaf: $LEAF"

# ---- tooling probes ------------------------------------------------------
for tool in tar zstd jq python3; do
  command -v "$tool" >/dev/null 2>&1 || err "$tool not found in PATH"
done
TAR_HELP="$(tar --help 2>/dev/null || true)"
if ! grep -q -- '--zstd' <<<"$TAR_HELP"; then
  err "tar lacks --zstd support. On Linux: install GNU tar 1.31+. On macOS: \`brew install gnu-tar\` and use \`gtar\`, or upgrade to libarchive bsdtar 3.5+."
fi
unset TAR_HELP

# sha256: prefer sha256sum (Linux), fall back to shasum (macOS), python3 last.
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

mkdir -p "$OUT_DIR"
TAR="$OUT_DIR/${TAG}.tar.zst"
MANIFEST="$OUT_DIR/${TAG}.manifest.json"

if [ -e "$TAR" ] && [ "$FORCE" = 0 ]; then
  err "$TAR already exists (use --force to overwrite)"
fi

# ---- count + size: capture stdout AND check exit status ------------------
# Using `read <<<"$(python3 ...)"` would mask a Python failure: the heredoc
# substitution swallows the non-zero exit and `read` succeeds on empty
# stdin, which would then look like "0 files" downstream.
COUNTS="$(python3 - "$SRC_REAL" <<'PY'
import os, sys
root = sys.argv[1]
n = 0
total = 0
for d, _, fs in os.walk(root):
    for f in fs:
        p = os.path.join(d, f)
        try:
            total += os.path.getsize(p)
            n += 1
        except OSError:
            pass
print(n, total)
PY
)" || err "failed to enumerate files under $SRC_REAL"

read -r N_FILES BYTES_UNC <<<"$COUNTS"
[ -n "${N_FILES:-}" ] && [ -n "${BYTES_UNC:-}" ] \
  || err "internal: empty counts from python ('$COUNTS')"
[ "$N_FILES" -gt 0 ] || err "$SRC_REAL contains no files"

GIT_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
CREATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# ---- pack ----------------------------------------------------------------
log "packing $SRC_REAL ($N_FILES files, $BYTES_UNC bytes uncompressed) -> $TAR"
tar --zstd -cf "$TAR" -C "$PARENT" "$LEAF"

BYTES_TAR="$(wc -c < "$TAR" | tr -d ' ')"
SHA256="$(sha256_file "$TAR")"

# Re-derive the on-repo source_path so the manifest doesn't leak the
# absolute path the script ran from.
SRC_REL="${SRC_REAL#"$REPO_ROOT/"}"

jq -n \
  --arg tag "$TAG" \
  --arg rq "$RQ" \
  --arg src "$SRC_REL" \
  --arg leaf "$LEAF" \
  --arg created "$CREATED_AT" \
  --arg sha "$GIT_SHA" \
  --argjson n_files "$N_FILES" \
  --argjson bytes_unc "$BYTES_UNC" \
  --argjson bytes_tar "$BYTES_TAR" \
  --arg sha256 "$SHA256" \
  --arg notes "$NOTES_INPUT" \
  '{
     tag: $tag,
     rq: $rq,
     source_path: $src,
     archive_root: $leaf,
     speca_commit: $sha,
     created_at: $created,
     n_files: $n_files,
     bytes_uncompressed: $bytes_unc,
     bytes_archive: $bytes_tar,
     archive_sha256: $sha256,
     compression: "zstd",
     notes: $notes
   }' > "$MANIFEST"

log "wrote manifest: $MANIFEST"
log "sha256: $SHA256"
log "done: $TAR ($BYTES_TAR bytes), compression ratio $(awk -v a="$BYTES_TAR" -v b="$BYTES_UNC" 'BEGIN{ if (a>0) printf "%.2fx\n", b/a; else print "n/a" }')"
