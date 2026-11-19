#!/bin/sh
# Check a content release candidate without publishing or signing OTA.
# Usage: tools/release_content.sh "Описание изменений"
set -eu
if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo 'Usage: tools/release_content.sh "Описание изменений"' >&2
  exit 2
fi
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
BRANCH=$(git branch --show-current)
if [ -z "$BRANCH" ] || [ "$BRANCH" = "main" ]; then
  echo 'Создайте рабочую ветку: подготовка в main запрещена.' >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo 'Есть незакоммиченные изменения: проверьте их перед подготовкой выпуска.' >&2
  exit 1
fi
# Syntax checks; build and OTA signing run in GitHub Actions after publication approval.
sh -n tools/release_content.sh
python3 - <<'PY'
import ast
from pathlib import Path
for filename in ('tools/ci_ota.py', 'tools/build_ota.py', 'web/build.py'):
    ast.parse(Path(filename).read_text(encoding='utf-8'), filename=filename)
print('Проверка синтаксиса Python пройдена')
PY
printf 'Проверен кандидат выпуска: %s\n' "$1"
printf 'Ветка: %s\n' "$BRANCH"
echo 'Ничего не опубликовано. Подготовьте Pull Request и дождитесь команды владельца «Опубликуй».'
