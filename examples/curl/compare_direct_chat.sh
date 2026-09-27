#!/bin/sh
set -eu
url="${1:-http://127.0.0.1:8080}"
requests="$(CDPATH= cd -- "$(dirname -- "$0")/../requests" && pwd)"
curl --fail-with-body --max-time 120 "${url%/}/decision" -H 'Content-Type: application/json' --data-binary "@$requests/boolean.json"
printf '\nInteractive comparison: sequential requests, direct generated tokens = 0 by design.\n'
curl --fail-with-body --max-time 120 "${url%/}/v1/chat/completions" -H 'Content-Type: application/json' --data-binary "@$requests/chat.json"
