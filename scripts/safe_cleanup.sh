#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TRASH_DIR="$HOME/.Trash"

DRY_RUN=1
INCLUDE_BUILD=0
INCLUDE_VENV=0
INCLUDE_MODELS=0

usage() {
  cat <<'EOF'
Usage: scripts/safe_cleanup.sh [options]

Safe workspace cleanup for Local Stereo Transcriber.

Defaults:
  - Dry-run only (no files moved)
  - Cleans lightweight generated files only

Options:
  --apply           Execute cleanup (move to macOS Trash)
  --dry-run         Show what would be cleaned (default)
  --include-build   Also clean build/ and dist/
  --include-venv    Also clean .venv/
  --include-models  Also clean local_models/
  -h, --help        Show this help text

Examples:
  scripts/safe_cleanup.sh
  scripts/safe_cleanup.sh --apply
  scripts/safe_cleanup.sh --apply --include-build
  scripts/safe_cleanup.sh --apply --include-build --include-models
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      DRY_RUN=0
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --include-build)
      INCLUDE_BUILD=1
      ;;
    --include-venv)
      INCLUDE_VENV=1
      ;;
    --include-models)
      INCLUDE_MODELS=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -d "$TRASH_DIR" ]]; then
  echo "ERROR: Trash directory not found: $TRASH_DIR" >&2
  exit 1
fi

declare -a targets=()
declare -a prune_args=()

# Always prune heavy directories during pattern scans.
prune_args+=( -path "$ROOT_DIR/.git" -o -path "$ROOT_DIR/.git/*" )
prune_args+=( -o -path "$ROOT_DIR/.venv" -o -path "$ROOT_DIR/.venv/*" )
prune_args+=( -o -path "$ROOT_DIR/local_models" -o -path "$ROOT_DIR/local_models/*" )
prune_args+=( -o -path "$ROOT_DIR/build" -o -path "$ROOT_DIR/build/*" )
prune_args+=( -o -path "$ROOT_DIR/dist" -o -path "$ROOT_DIR/dist/*" )

# Lightweight generated noise.
while IFS= read -r -d '' f; do
  targets+=("$f")
done < <(find "$ROOT_DIR" \( "${prune_args[@]}" \) -prune -o -type d -name '__pycache__' -print0)

while IFS= read -r -d '' f; do
  targets+=("$f")
done < <(find "$ROOT_DIR" \( "${prune_args[@]}" \) -prune -o -type f -name '*.pyc' -print0)

while IFS= read -r -d '' f; do
  targets+=("$f")
done < <(find "$ROOT_DIR" \( "${prune_args[@]}" \) -prune -o -type f -name '.DS_Store' -print0)

while IFS= read -r -d '' f; do
  targets+=("$f")
done < <(find "$ROOT_DIR" \( "${prune_args[@]}" \) -prune -o -type f -name 'ui_trace.log*' -print0)

if [[ "$INCLUDE_BUILD" -eq 1 ]]; then
  [[ -e "$ROOT_DIR/build" ]] && targets+=("$ROOT_DIR/build")
  [[ -e "$ROOT_DIR/dist" ]] && targets+=("$ROOT_DIR/dist")
fi

if [[ "$INCLUDE_VENV" -eq 1 && -e "$ROOT_DIR/.venv" ]]; then
  targets+=("$ROOT_DIR/.venv")
fi

if [[ "$INCLUDE_MODELS" -eq 1 && -e "$ROOT_DIR/local_models" ]]; then
  targets+=("$ROOT_DIR/local_models")
fi

# De-duplicate targets while preserving order (Bash 3.2 compatible).
declare -a unique_targets=()
for item in "${targets[@]-}"; do
  already_seen=0
  for existing in "${unique_targets[@]-}"; do
    if [[ "$existing" == "$item" ]]; then
      already_seen=1
      break
    fi
  done
  if [[ "$already_seen" -eq 0 ]]; then
    unique_targets+=("$item")
  fi
done

if [[ ${#unique_targets[@]-0} -eq 0 ]]; then
  echo "Nothing to clean."
  exit 0
fi

echo "Cleanup mode: $([[ "$DRY_RUN" -eq 1 ]] && echo 'dry-run' || echo 'apply')"
echo "Items selected: ${#unique_targets[@]}"
echo

for item in "${unique_targets[@]-}"; do
  size="$(du -sh "$item" 2>/dev/null | awk '{print $1}')"
  [[ -z "$size" ]] && size="-"
  rel="${item#"$ROOT_DIR"/}"
  [[ "$item" == "$ROOT_DIR" ]] && rel="."
  echo "- $rel ($size)"
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "Dry-run only. Re-run with --apply to move these items to Trash."
  exit 0
fi

echo
echo "Moving selected items to Trash..."
for item in "${unique_targets[@]}"; do
  [[ -e "$item" ]] || continue
  base_name="$(basename "$item")"
  dest_path="$TRASH_DIR/$base_name"
  if [[ -e "$dest_path" ]]; then
    dest_path="$TRASH_DIR/${base_name}_$(date +%s)_$RANDOM"
  fi
  mv "$item" "$dest_path"
done

echo "Done. Items moved to Trash: ${#unique_targets[@]}"