#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH="$PWD/integration/medical-platform:$PWD/integration/medical-platform/testdeps"
export MEDICAL_YDB_LOCAL_PORT=2136
export PYTHONDONTWRITEBYTECODE=1
python -m pip install ydb==3.35.0 argon2-cffi==25.1.0
npm install --prefix "$RUNNER_TEMP/medical-webview" --no-audit --no-fund playwright@1.60.0
export NODE_PATH="$RUNNER_TEMP/medical-webview/node_modules"
docker run -d --name medical-ydb --hostname localhost -p 127.0.0.1:2136:2136 \
  -e GRPC_PORT=2136 -e YDB_GRPC_ENABLE_TLS=false -e YDB_USE_IN_MEMORY_PDISKS=true ydbplatform/local-ydb:26.2.1.16
trap 'docker logs --tail 70 medical-ydb; docker rm -f medical-ydb' EXIT
for i in $(seq 1 60); do
  [[ "$(docker inspect --format '{{.State.Health.Status}}' medical-ydb)" == healthy ]] && break
  sleep 2
done
[[ "$(docker inspect --format '{{.State.Health.Status}}' medical-ydb)" == healthy ]]
python -m unittest -v 077_android_e2e
