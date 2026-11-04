#!/bin/sh
# Builds the release APK and publishes it to the `apk` branch (one commit, replaced each time).
# The Pages workflow then puts it at <site>/download/SpravochnikNMP.apk and <site>/android.json,
# which installed apps check on launch.
#   tools/publish_apk.sh "что нового (одна строка)"
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SITE=https://victorpolekslab.github.io/Spravochnik_nmp
cd "$ROOT/android"
gradle --no-daemon -q assembleRelease
APK=app/build/outputs/apk/release/app-release.apk
CODE=$(sed -n 's/.*versionCode \([0-9]*\).*/\1/p' app/build.gradle)
NAME=$(sed -n 's/.*versionName "\([^"]*\)".*/\1/p' app/build.gradle)
TMP=$(mktemp -d)
cp "$APK" "$TMP/SpravochnikNMP.apk"
python3 - "$TMP/android.json" "$CODE" "$NAME" "$1" "$SITE" <<'PY'
import json, sys
p, code, name, notes, site = sys.argv[1:]
json.dump({"versionCode": int(code), "versionName": name, "notes": notes,
           "url": site + "/download/SpravochnikNMP.apk"}, open(p, "w"), ensure_ascii=False)
PY
cd "$TMP"
git init -q -b apk
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-victorpolekslab}" -c user.email="${GIT_AUTHOR_EMAIL:-342812774+victorpolekslab@users.noreply.github.com}" \
  commit -qm "APK $NAME"
git push -f "$(git -C "$ROOT" remote get-url origin)" apk:apk
echo "published $NAME ($CODE)"
