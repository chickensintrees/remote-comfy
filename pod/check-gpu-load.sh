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
# CURRENT COMFYUI NO LONGER PRINTS "loaded completely/partially" - its dynamic-VRAM loader
# logs "prepared for dynamic VRAM loading. NNNNMB Staged" instead (seen on 0.42.0,
# 2026-10-23). A check keyed only on the old line could never pass and blamed CPU
# streaming that was not happening. So the primary signal is now SPEED PARITY: every
# instance runs the same model on the same card, so one shard far slower than the
# fastest is the degradation itself, whatever the log wording. The old line is still
# honoured when present.
#
#   bash check-gpu-load.sh <host> <port> [logglob]
#   CHECK_GPU_LOAD_INPUT=<file> bash check-gpu-load.sh - -    # offline: "log|loadline|rate"
#
# Exit 0 = every instance has a rate within SLOW_RATIO (default 0.7) of the fastest and
# none reports "loaded partially". Exit 1 = degraded, or no signal yet (a missing signal
# is NOT a pass). Fix: pkill -f 'main\.py.*--listen', confirm nvidia-smi shows no compute
# apps, relaunch.
set -u
HOST="${1:?host}"; PORT="${2:?ssh port}"; GLOB="${3:-/workspace/comfy_g*.log}"
SLOW_RATIO="${SLOW_RATIO:-0.7}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"

if [ -n "${CHECK_GPU_LOAD_INPUT:-}" ]; then
  OUT=$(cat "$CHECK_GPU_LOAD_INPUT")
else
  # one line per log: <log>|<last old-style load line>|<last tqdm rate, e.g. 1.18it/s>
  OUT=$(ssh $SSHOPT -p "$PORT" root@"$HOST" "
    for L in $GLOB; do
      [ -e \"\$L\" ] || continue
      LOAD=\$(grep -aE 'loaded (completely|partially)' \"\$L\" | tail -n 1)
      RATE=\$(grep -aoE '[0-9]+(\.[0-9]+)?(it/s|s/it)' \"\$L\" | tail -n 1)
      echo \"\$L|\$LOAD|\$RATE\"
    done" 2>/dev/null)
fi

if [ -z "$OUT" ]; then
  echo "check-gpu-load: NO LOGS FOUND in $GLOB - nothing has launched, or the path is wrong."
  echo "  A missing signal is NOT a pass."
  exit 1
fi

# normalise each rate to it/s, then judge against the fastest instance
echo "$OUT" | awk -F'|' -v ratio="$SLOW_RATIO" '
  { log_[NR]=$1; load[NR]=$2; r=$3; v=0
    if (r ~ /it\/s$/) { sub(/it\/s$/, "", r); v=r+0 }
    else if (r ~ /s\/it$/) { sub(/s\/it$/, "", r); if (r+0 > 0) v=1/(r+0) }
    rate[NR]=v; if (v > best) best=v; n=NR }
  END {
    bad=0
    for (i=1; i<=n; i++) {
      if (load[i] ~ /loaded partially/) { printf "DEGRADED  %s  (%s)\n", log_[i], load[i]; bad=1 }
      else if (rate[i] == 0)            { printf "NO SIGNAL %s  (no sampling rate yet)\n", log_[i]; bad=1 }
      else if (rate[i] < ratio*best)    { printf "SLOW      %s  %.2f it/s vs fastest %.2f\n", log_[i], rate[i], best; bad=1 }
      else                              { printf "ok        %s  %.2f it/s\n", log_[i], rate[i] }
    }
    if (bad) {
      print ""
      print "Degraded or not yet sampling. A slow shard is usually a VRAM squatter forcing a"
      print "partial load: do not project throughput from the fast shard. Kill every"
      print "main.py --listen, check  nvidia-smi --query-compute-apps=pid,used_memory --format=csv"
      print "shows nothing, relaunch, and re-run this once sampling has started."
      exit 1
    }
    print "all instances sampling at matching speed"
  }'
