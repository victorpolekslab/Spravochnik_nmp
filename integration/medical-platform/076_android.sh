#!/usr/bin/env bash
set -euo pipefail
apk="${1:?debug APK path required}"
evidence="${2:-android-audit}"
mkdir -p "$evidence"
sdk="${ANDROID_HOME:?set ANDROID_HOME}"
export PATH="$sdk/platform-tools:$sdk/emulator:$PATH"
package=$("$sdk/build-tools/35.0.0/aapt" dump badging "$apk" | sed -n "s/^package: name='\([^']*\)'.*/\1/p")
test -n "$package"
sha256sum "$apk"
if [[ "${MEDICAL_ANDROID_START_EMULATOR:-0}" == 1 ]]; then
  if [[ ! -c /dev/kvm ]]; then echo "ANDROID BLOCKED: /dev/kvm absent"; exit 0; fi
  sudo chmod a+rw /dev/kvm
  sdkmanager --install platform-tools emulator 'system-images;android-34;google_apis;x86_64'
  echo no | avdmanager create avd --force -n medical-audit -k 'system-images;android-34;google_apis;x86_64'
  emulator -avd medical-audit -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -no-snapshot >"$evidence/emulator.txt" 2>&1 &
  trap 'adb emu kill || true' EXIT
fi
timeout 180 adb wait-for-device
for i in $(seq 1 90); do
  [[ "$(adb shell getprop sys.boot_completed | tr -d '\r')" == 1 ]] && break
  sleep 2
done
[[ "$(adb shell getprop sys.boot_completed | tr -d '\r')" == 1 ]]
adb shell getprop ro.build.version.sdk
adb shell getprop ro.product.cpu.abi
adb install -r "$apk"
adb shell wm dismiss-keyguard || true
launch() {
  adb shell am force-stop "$package"
  adb shell monkey -p "$package" -c android.intent.category.LAUNCHER 1
  sleep 5
  adb shell pidof "$package"
  adb shell uiautomator dump /sdcard/medical-audit.xml
  adb exec-out cat /sdcard/medical-audit.xml >"$evidence/${1}.xml"
  grep -q 'package="'"$package"'"' "$evidence/${1}.xml"
  adb exec-out screencap -p >"$evidence/${1}.png"
}
launch online
if [[ "${MEDICAL_ANDROID_START_EMULATOR:-0}" == 1 ]]; then
  adb shell svc wifi disable
  adb shell svc data disable
  launch offline
  adb shell svc wifi enable
  adb shell svc data enable
  launch restored
fi
adb logcat -d -t 500 >"$evidence/logcat.txt"
echo "ANDROID_RUNTIME PASS install, launcher, process restart"
