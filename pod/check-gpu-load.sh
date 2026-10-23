#!/usr/bin/env bash
# Fail if any per-GPU ComfyUI instance loaded its model PARTIALLY instead of completely.
#
# WHY THIS EXISTS (2026-07-26, cost ~35 min of a 2-GPU render at half throughput):
# ComfyUI decides how much VRAM is "usable" from the FREE VRAM at model-load time, once.
# A stale ComfyUI from an earlier run was still squatting ~22 GB on GPU0 when the new
# instance booted, so that instance saw only 22.9 GB usable and ran FLUX.2 (33.8 GB)
# PARTIALLY LOADED - 11.8 GB offloaded to CPU, weights streamed every step:
#
#   GPU1  loaded completely; 37375 MB usable, 33813 MB loaded   -> 127 s/frame
#   GPU0  loaded partially;  22880 MB usable, 11781 MB offloaded -> 494 s/frame  (3.9x)
#
# Both GPUs showed 100% utilisation and neither log showed an error. The ONLY signal was
# this line. nvidia-smi cannot tell you this; a busy GPU thrashing PCIe looks identical to
# a fast one. ALWAYS run this after launching per-GPU instances and BEFORE trusting any
# throughput projection - a half-speed shard doubles the bill silently.
#
#   bash check-gpu-load.sh <host> <port> [logglob]
#
# Exit 0 = every instance loaded completely. Exit 1 = at least one is degraded; kill the
# stale squatters (pkill -f 'main.py --listen'), confirm nvidia-smi shows no compute apps,
# and relaunch.
set -u
HOST="${1:?host}"; PORT="${2:?ssh port}"; GLOB="${3:-/workspace/comfy_g*.log}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"

OUT=$(ssh $SSHOPT -p "$PORT" root@"$HOST" "
  for L in $GLOB; do
    [ -e \"\$L\" ] || continue
    LAST=\$(grep -E 'loaded (completely|partially)' \"\$L\" | tail -1)
    echo \"\$L|\$LAST\"
  done" 2>/dev/null)

if [ -z "$OUT" ]; then
  echo "check-gpu-load: NO LOAD LINES FOUND in $GLOB - models have not loaded yet (or the"
  echo "  log path is wrong). A missing signal is NOT a pass; re-run once loading starts."
  exit 1
fi

BAD=0
while IFS= read -r line; do
  LOG="${line%%|*}"; MSG="${line#*|}"
  case "$MSG" in
    *"loaded partially"*)
      echo "DEGRADED  $LOG"
      echo "          $MSG"
      BAD=1 ;;
    *"loaded completely"*)
      echo "ok        $LOG" ;;
    *)
      echo "UNKNOWN   $LOG (no load line) "; BAD=1 ;;
  esac
done <<EOF
$OUT
EOF

if [ "$BAD" -ne 0 ]; then
  echo
  echo "At least one instance is streaming weights from CPU. Do not project throughput from"
  echo "the fast shard. Kill every 'main.py --listen', verify with:"
  echo "  nvidia-smi --query-compute-apps=pid,used_memory --format=csv"
  echo "that no process still holds VRAM, then relaunch."
  exit 1
fi
echo "all instances loaded completely"
