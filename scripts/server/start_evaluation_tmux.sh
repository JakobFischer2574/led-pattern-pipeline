#!/usr/bin/env bash
set -euo pipefail

SESSION="led-eval"
RUN_NAME=""
CONFIG="configs/server.yaml"
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --session) SESSION="$2"; shift 2 ;;
    --run-name) RUN_NAME="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --config) CONFIG="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

if ! command -v tmux >/dev/null 2>&1; then
  echo "ERROR: tmux is not installed." >&2
  exit 1
fi
if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "ERROR: tmux session '${SESSION}' already exists. Attach to it or choose another --session name." >&2
  exit 2
fi
if [[ -z "${RUN_NAME}" ]]; then
  RUN_NAME="$(python - <<'PY' "${CONFIG}"
import sys, yaml
from pathlib import Path
cfg = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
print((cfg.get('run') or {}).get('name') or 'server_run')
PY
)"
fi
OUTPUT_ROOT="$(python - <<'PY' "${CONFIG}"
import sys, yaml
from pathlib import Path
cfg = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
print((cfg.get('outputs') or {}).get('root') or 'outputs')
PY
)"
CMD="cd '$(pwd)' && bash scripts/server/run_evaluation_server.sh ${ARGS[*]}; echo; echo 'Evaluation finished. Press Ctrl-b d to detach or close this pane manually.'"
tmux new-session -d -s "${SESSION}" "${CMD}"
tmux set-option -t "${SESSION}" remain-on-exit on

echo "Started tmux session: ${SESSION}"
echo "Attach:       tmux attach -t ${SESSION}"
echo "Capture pane: tmux capture-pane -pt ${SESSION}"
echo "Follow log:   tail -f ${OUTPUT_ROOT}/${RUN_NAME}/server_run.log"
