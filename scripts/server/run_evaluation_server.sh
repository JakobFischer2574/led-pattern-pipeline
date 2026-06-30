#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

CONFIG="configs/server.yaml"
RUN_NAME=""
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --run-name) RUN_NAME="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: Git working tree is not clean. Commit or stash changes before server execution." >&2
  git status --short >&2
  exit 2
fi

git fetch --prune
git pull --ff-only

if find . -name .gitattributes -not -path './.git/*' -exec grep -H 'filter=lfs' {} + 2>/dev/null | grep -q 'filter=lfs'; then
  if ! git lfs version >/dev/null 2>&1; then
    echo "ERROR: Git LFS files are configured, but git-lfs is not installed. Install it and run 'git lfs pull'." >&2
    exit 3
  fi
  git lfs pull
fi

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
PYTHON_BIN="${PYTHON_BIN:-python}"

"${PYTHON_BIN}" - <<'PY' "${CONFIG}"
import sys
from pathlib import Path
import yaml
cfg = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
missing = []
for key in ("ground_truth_csv", "video_dir"):
    path = Path(str(cfg.get("data", {}).get(key, "")))
    if not path.exists():
        missing.append(f"data.{key}: {path}")
for cfg_key in ("classic_cv_config", "yolo_config", "led_layout", "temporal_config", "error_codes_config"):
    path = Path(str(cfg.get(cfg_key, "")))
    if path and not path.exists():
        missing.append(f"{cfg_key}: {path}")
out = Path(str(cfg.get("outputs", {}).get("root", "outputs")))
out.mkdir(parents=True, exist_ok=True)
if missing:
    print("ERROR: Required input paths are missing. Provide videos/models via mount or rsync before starting:", file=sys.stderr)
    print("\n".join(f"  - {m}" for m in missing), file=sys.stderr)
    sys.exit(4)
PY

if [[ -z "${RUN_NAME}" ]]; then
  RUN_NAME="$(${PYTHON_BIN} - <<'PY' "${CONFIG}"
import sys, yaml
from pathlib import Path
cfg = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
print((cfg.get('run') or {}).get('name') or 'server_run')
PY
)"
fi
OUTPUT_ROOT="$(${PYTHON_BIN} - <<'PY' "${CONFIG}"
import sys, yaml
from pathlib import Path
cfg = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
print((cfg.get('outputs') or {}).get('root') or 'outputs')
PY
)"
mkdir -p "${OUTPUT_ROOT}/${RUN_NAME}"
LOG_FILE="${OUTPUT_ROOT}/${RUN_NAME}/server_run.log"
set +e
"${PYTHON_BIN}" scripts/run_pipeline.py "${ARGS[@]}" 2>&1 | tee "${LOG_FILE}"
status=${PIPESTATUS[0]}
set -e
echo "Pipeline exit code: ${status}"
exit "${status}"
