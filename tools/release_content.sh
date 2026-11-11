#!/bin/sh
# Выпуск изменений содержимого справочника БЕЗ нового APK: Android 4.1+ скачает их в фоне,
# веб-версия обновится через service worker.
#   tools/release_content.sh "что изменилось (одна строка)"
# Новый APK (tools/publish_apk.sh) нужен только при изменениях Java-кода или базы КР (cr.db).
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
python3 tools/build_ota.py
(cd web && python3 build.py >/dev/null)
git add -A android/app/src/main/assets/www ota
git commit -qm "Содержимое: $1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01LvhX437HMkLWukqEN9eDLL"
git push -q origin main
echo "content released: $(cat android/app/src/main/assets/www/ota_version.txt)"
