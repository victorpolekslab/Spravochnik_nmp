#!/bin/sh
# Prepare a content release locally; publication happens only after approved changes
# are merged into main. The Pages workflow deploys on push to main.
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
  echo 'Создайте рабочую ветку: публикация напрямую из main запрещена.' >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo 'Есть незакоммиченные изменения. Сначала сохраните или отдельно проверьте их.' >&2
  exit 1
fi
python3 tools/build_ota.py
(cd web && python3 build.py >/dev/null)
git add android/app/src/main/assets/www/ota_version.txt ota
if git diff --cached --quiet; then
  echo 'Нет изменений для подготовки выпуска.'
else
  git commit -m "Подготовка содержимого: $1"
fi
echo "Подготовлено в ветке $BRANCH. Ничего не отправлено в main."
echo 'Создайте Pull Request и публикуйте только по разрешению владельца.'
