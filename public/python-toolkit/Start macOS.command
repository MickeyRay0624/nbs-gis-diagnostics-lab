#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
PYTHON=""
for candidate in python3.12 python3.13 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo 'Install Python 3.12 from https://www.python.org/downloads/ then open this file again.'
else
  "$PYTHON" run.py
fi
read -r -p 'Press Enter to close this window.'
