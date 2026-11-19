#!/bin/sh
# Prepare content changes in a feature branch. Publishing is performed by
# the GitHub Pages workflow after the owner authorizes merging into main.
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
# PWA and signed Android OTA are built by the Pages workflow using the
# protected OTA_KEY_PEM secret. Do not sign or publish from this script.
echo "Ветка $BRANCH готова к проверке."
echo 'Создайте Pull Request. Слияние в main и публикация — только по разрешению владельца.'
