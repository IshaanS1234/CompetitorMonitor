#!/bin/zsh

set -u

MONITOR_PROJECT_DIR=${0:A:h}
MONITOR_LOG_DIR="$MONITOR_PROJECT_DIR/automation_logs"
MONITOR_STATE_FILE="$MONITOR_LOG_DIR/last_successful_run.txt"
MONITOR_TODAY=$(/bin/date '+%Y-%m-%d')
MONITOR_YESTERDAY=$(/bin/date -v-1d '+%Y-%m-%d')
MONITOR_CURRENT_HOUR=$(/bin/date '+%H')
MONITOR_TIMESTAMP=$(/bin/date '+%Y-%m-%d_%H-%M-%S')
MONITOR_LOG_FILE="$MONITOR_LOG_DIR/run_$MONITOR_TIMESTAMP.log"

/bin/mkdir -p "$MONITOR_LOG_DIR"

MONITOR_LAST_SUCCESS=""
if [[ -f "$MONITOR_STATE_FILE" ]]; then
  MONITOR_LAST_SUCCESS=$(/bin/cat "$MONITOR_STATE_FILE")
fi

# Do not run twice on the same day. Before 3 PM, only run at login when
# yesterday's scheduled check was missed.
if [[ "$MONITOR_LAST_SUCCESS" == "$MONITOR_TODAY" ]]; then
  exit 0
fi
if (( 10#$MONITOR_CURRENT_HOUR < 15 )) && [[ "$MONITOR_LAST_SUCCESS" == "$MONITOR_YESTERDAY" ]]; then
  exit 0
fi

{
  echo "Daily competitor monitor started at $(/bin/date)"

  if ! /usr/bin/curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
    MONITOR_OLLAMA_BIN=""
    if [[ -x /usr/local/bin/ollama ]]; then
      MONITOR_OLLAMA_BIN=/usr/local/bin/ollama
    elif [[ -x /opt/homebrew/bin/ollama ]]; then
      MONITOR_OLLAMA_BIN=/opt/homebrew/bin/ollama
    fi

    if [[ -n "$MONITOR_OLLAMA_BIN" ]]; then
      echo "Ollama was not responding, so the runner is starting it."
      "$MONITOR_OLLAMA_BIN" serve >>"$MONITOR_LOG_DIR/ollama.log" 2>&1 &

      for MONITOR_ATTEMPT in {1..20}; do
        if /usr/bin/curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null; then
          echo "Ollama is ready."
          break
        fi
        /bin/sleep 1
      done
    else
      echo "Ollama is not installed in an expected location."
    fi
  else
    echo "Ollama is already ready."
  fi

  cd "$MONITOR_PROJECT_DIR" || exit 1
  "$MONITOR_PROJECT_DIR/.venv/bin/python" "$MONITOR_PROJECT_DIR/run_monitor.py"
  MONITOR_EXIT_CODE=$?

  if [[ $MONITOR_EXIT_CODE -eq 0 ]]; then
    printf '%s\n' "$MONITOR_TODAY" >"$MONITOR_STATE_FILE"
  fi

  echo "Daily competitor monitor finished at $(/bin/date) with status $MONITOR_EXIT_CODE."
  exit $MONITOR_EXIT_CODE
} >>"$MONITOR_LOG_FILE" 2>&1
