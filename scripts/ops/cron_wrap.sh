#!/usr/bin/env bash
# Runs a cron command and reports it to Healthchecks.io.
# Usage: cron_wrap.sh <ping-url> <command> [args...]
#   ping-url: https://hc-ping.com/<uuid> (empty string = run without reporting)
# Healthchecks emails when a run fails (non-zero exit) or does not happen on
# schedule. The end of the output is sent with the ping so the email shows why.
set -uo pipefail

url=$1
shift

ping() {
    [ -n "$url" ] || return 0
    curl -fsS -m 10 --retry 3 -o /dev/null "$@" || true  # monitoring must never fail the job
}

ping "$url/start"
log=$(mktemp)
"$@" 2>&1 | tee "$log"  # output still reaches the cron log file
code=${PIPESTATUS[0]}
tail -c 10000 "$log" | ping --data-binary @- "$url/$code"
rm -f "$log"
exit "$code"
