#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
CAFFEINATE_BIN="/usr/bin/caffeinate"
ENV_FILE="$PROJECT_DIR/.env"
CURATOR_KEY_ENV="AUTOMATION_BRIEF_CURATOR_API_KEY"
REPORT_TYPE=${1:-digest}

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [digest|overnight_brief]" >&2
  exit 2
fi

case "$REPORT_TYPE" in
  digest|overnight_brief)
    ;;
  *)
    echo "Unsupported report type: $REPORT_TYPE" >&2
    exit 2
    ;;
esac

read_env_value() {
  env_file_path=$1
  env_key=$2
  if [ ! -r "$env_file_path" ]; then
    return 0
  fi

  env_value=$(
    awk -v wanted="$env_key" '
      {
        line = $0
        sub(/^[[:space:]]+/, "", line)
        sub(/[[:space:]]+$/, "", line)
        if (line == "" || substr(line, 1, 1) == "#") {
          next
        }

        equals = index(line, "=")
        if (equals == 0) {
          next
        }

        name = substr(line, 1, equals - 1)
        value = substr(line, equals + 1)
        sub(/^[[:space:]]+/, "", name)
        sub(/[[:space:]]+$/, "", name)
        sub(/^[[:space:]]+/, "", value)
        sub(/[[:space:]]+$/, "", value)

        if (name == wanted) {
          first = substr(value, 1, 1)
          last = substr(value, length(value), 1)
          single_quote = sprintf("%c", 39)
          if ((first == "\"" && last == "\"") || (first == single_quote && last == single_quote)) {
            value = substr(value, 2, length(value) - 2)
          }
          print value
          exit
        }
      }
    ' "$env_file_path"
  )
  printf '%s\n' "$env_value"
}

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python executable not found or not executable: $PYTHON_BIN" >&2
  exit 1
fi

if [ "${AUTOMATION_BRIEF_CAFFEINATED:-0}" != "1" ]; then
  if [ ! -x "$CAFFEINATE_BIN" ]; then
    echo "caffeinate executable not found or not executable: $CAFFEINATE_BIN" >&2
    exit 1
  fi
  export AUTOMATION_BRIEF_CAFFEINATED=1
  exec "$CAFFEINATE_BIN" -dimsu "$0" "$@"
fi

timestamp() {
  date "+%Y-%m-%dT%H:%M:%S%z"
}

log_stage() {
  printf "%s %s\n" "$(timestamp)" "$*"
}

TASK_START_EPOCH=$(date "+%s")

log_task_end() {
  task_exit_code=$?
  task_end_epoch=$(date "+%s")
  task_elapsed=$((task_end_epoch - TASK_START_EPOCH))
  log_stage "task end exit_code=$task_exit_code elapsed_seconds=$task_elapsed"
}

trap log_task_end 0

cd "$PROJECT_DIR"
log_stage "task start"

if [ "$REPORT_TYPE" = "overnight_brief" ]; then
  if [ -n "${AUTOMATION_BRIEF_CURATOR_API_KEY:-}" ]; then
    log_stage "curator credential available"
  else
    curator_api_key=$(read_env_value "$ENV_FILE" "$CURATOR_KEY_ENV")
    if [ -n "$curator_api_key" ]; then
      export AUTOMATION_BRIEF_CURATOR_API_KEY="$curator_api_key"
      log_stage "curator credential available"
    else
      log_stage "curator credential unavailable; fallback remains available"
    fi
    curator_api_key=""
  fi
fi

main_start_epoch=$(date "+%s")
log_stage "main.py start"
if "$PYTHON_BIN" "$PROJECT_DIR/main.py" --report-type "$REPORT_TYPE"; then
  main_exit_code=0
else
  main_exit_code=$?
fi
main_end_epoch=$(date "+%s")
log_stage "main.py end exit_code=$main_exit_code elapsed_seconds=$((main_end_epoch - main_start_epoch))"
if [ "$main_exit_code" -ne 0 ]; then
  exit "$main_exit_code"
fi

publish_start_epoch=$(date "+%s")
log_stage "publish_mobile_digest.py start"
if "$PYTHON_BIN" "$PROJECT_DIR/scripts/publish_mobile_digest.py" --report-type "$REPORT_TYPE"; then
  publish_exit_code=0
else
  publish_exit_code=$?
  echo "Mobile digest sync failed; daily report was already generated." >&2
fi
publish_end_epoch=$(date "+%s")
log_stage "publish_mobile_digest.py end exit_code=$publish_exit_code elapsed_seconds=$((publish_end_epoch - publish_start_epoch))"

bark_start_epoch=$(date "+%s")
log_stage "send_bark_notification.py start"
if "$PYTHON_BIN" "$PROJECT_DIR/scripts/send_bark_notification.py" --report-type "$REPORT_TYPE"; then
  bark_exit_code=0
else
  bark_exit_code=$?
  echo "Bark notification failed; daily report was already generated." >&2
fi
bark_end_epoch=$(date "+%s")
log_stage "send_bark_notification.py end exit_code=$bark_exit_code elapsed_seconds=$((bark_end_epoch - bark_start_epoch))"
