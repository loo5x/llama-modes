#!/bin/sh
set -eu
url="${1:-http://127.0.0.1:8080}"
requests="$(CDPATH= cd -- "$(dirname -- "$0")/../requests" && pwd)"
curl --fail-with-body --max-time 120 "${url%/}/scale" -H 'Content-Type: application/json' --data-binary "@$requests/scale.json"
