#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'; then
  echo '请先从 python.org 安装 Python 3.12 或更新版本。'
  exit 1
fi
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
if ! .venv/bin/python -c 'import lxml, openpyxl, pypdf, xlrd' >/dev/null 2>&1; then
  echo '首次运行，正在安装公告解析组件……'
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python scripts/launch.py
