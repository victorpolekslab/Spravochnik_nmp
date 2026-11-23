#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p "$1"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=Medical-Pilot-Test-CA \
  -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign \
  -keyout "$1/ca.key" -out "$1/ca.pem" 2>/dev/null
openssl req -newkey rsa:2048 -nodes -subj /CN=localhost -keyout "$1/server.key" -out "$1/server.csr" 2>/dev/null
printf '%s\n' 'basicConstraints=critical,CA:FALSE' 'extendedKeyUsage=serverAuth' 'subjectAltName=DNS:localhost' > "$1/server.ext"
openssl x509 -req -days 1 -in "$1/server.csr" -CA "$1/ca.pem" -CAkey "$1/ca.key" \
  -CAcreateserial -extfile "$1/server.ext" -out "$1/server.pem" 2>/dev/null
rm "$1/ca.key"
if [[ $# == 2 ]]; then
  debug="$2/android/app/src/debug/res"
  mkdir -p "$debug/raw"
  install -m 0644 "$1/ca.pem" "$debug/raw/pilot_ca.pem"
  cat > "$debug/xml/pilot_debug_network.xml" <<'XML'
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <domain-config cleartextTrafficPermitted="true">
        <domain>localhost</domain>
        <trust-anchors><certificates src="@raw/pilot_ca" /></trust-anchors>
    </domain-config>
</network-security-config>
XML
fi
