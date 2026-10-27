#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"
if command -v python3.13 >/dev/null 2>&1; then
  exec python3.13 scripts/run.py "$@"
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/run.py "$@"
fi
echo 'Для запуска нужен Python 3.13. Откройте README.md.'
exit 1
