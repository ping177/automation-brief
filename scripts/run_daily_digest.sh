#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python executable not found or not executable: $PYTHON_BIN" >&2
  exit 1
fi

cd "$PROJECT_DIR"
"$PYTHON_BIN" "$PROJECT_DIR/main.py"

if ! "$PYTHON_BIN" "$PROJECT_DIR/scripts/publish_mobile_digest.py"; then
  echo "Mobile digest sync failed; daily report was already generated." >&2
fi

if ! "$PYTHON_BIN" "$PROJECT_DIR/scripts/send_bark_notification.py"; then
  echo "Bark notification failed; daily report was already generated." >&2
fi
