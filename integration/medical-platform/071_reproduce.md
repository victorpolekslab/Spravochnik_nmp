# Stage 7.1 · isolated checks

Run from the extracted export directory. `source/nmp` takes precedence over stage 5–6 on PYTHONPATH because this pilot overlays the session and learning digest modules. The original dependencies remain in the export for comparison. No cloud endpoint is used.

```sh
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD/source/nmp:$PWD/source/stage5:$PWD/source/stage6:$PWD/source/reference"
python -m unittest -v 071_test_gateway_model 071_test_keyring 06_test_learning 07_test_sync_queue
node --test source/nmp/07_test_client.mjs
node --test source/terapevt/07_test_client.mjs
# Requires Chromium, Playwright and a host allowing a fresh Chromium profile:
node --test source/nmp/071_test_browser.cjs
# Requires ydb==3.35.0, argon2-cffi==25.1.0 and a dedicated loopback YDB /local:
MEDICAL_YDB_LOCAL_PORT=32136 python -m unittest -v 07_test_gateway 05_test_ydb 06_test_ydb 05_test_registration
```

The runner remains for loopback only. Set the five active secret variables documented in the stage-7 integration report. Optional comma-separated verification-only lists (base64 independent 32-byte keys, up to three per purpose): `MEDICAL_PILOT_RETIRED_ACCESS_KEYS`, `MEDICAL_PILOT_RETIRED_REFRESH_KEYS`, `MEDICAL_PILOT_RETIRED_DIGEST_KEYS`. Seal new tokens and grade new attempts with the active keys. For a rolling deployment, provision both old and future keys for verification on every worker before switching the signing key. Keep retired access/refresh keys until the last possible token expiry, and digest keys for the full retry retention window (or preserve indefinitely if no attempted-submit retention window is established). Registration and recovery keys require an independent rotation procedure. The pilot cookie handles remain process-local even with these keyrings.
