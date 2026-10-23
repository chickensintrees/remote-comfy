#!/usr/bin/env bash
# Hold /workspace/.busy alive for as long as a job is actually running, then release it.
#
# WHY (2026-07-27, cost ~3h of idle H100 = ~$9): a sweep script did `touch /workspace/.busy`
# at the top and exited without removing it. The watchdog saw the lock, "held", and kept a
# completely idle pod billing for three hours. A lock that outlives its job is
# indistinguishable from one nobody cleaned up.
#
# So the lock is a HEARTBEAT: autostop ignores it once it is older than --lock-ttl-min.
# This refreshes it while the work runs, and clears it on exit — including on Ctrl-C, on
# error, and on SIGTERM, which is the case a naive `touch ... ; job ; rm ...` gets wrong.
#
#   bash hold-busy.sh -- <command> [args...]     # hold while the command runs
#   bash hold-busy.sh --pid 12345                # hold while an existing PID lives
#
# Never leaves the lock behind. If this script is SIGKILLed the lock simply goes stale on
# its own, which is the whole point of the TTL.
set -u
LOCK=/workspace/.busy
INTERVAL="${HOLD_INTERVAL:-60}"

release(){ rm -f "$LOCK"; }
trap release EXIT INT TERM

beat(){ while true; do touch "$LOCK"; sleep "$INTERVAL"; done; }

if [ "${1:-}" = "--pid" ]; then
  WATCH="${2:?pid}"
  touch "$LOCK"; beat & BEAT=$!
  while kill -0 "$WATCH" 2>/dev/null; do sleep 5; done
  kill "$BEAT" 2>/dev/null
  exit 0
fi

[ "${1:-}" = "--" ] && shift
[ $# -gt 0 ] || { echo "usage: hold-busy.sh -- <command> [args...]  |  --pid <pid>" >&2; exit 2; }

touch "$LOCK"; beat & BEAT=$!
"$@"; rc=$?
kill "$BEAT" 2>/dev/null
exit "$rc"
