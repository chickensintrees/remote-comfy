#!/usr/bin/env bash
# Run ONE ComfyUI per GPU and shard a batch harness across them. Copy to the pod and run
# detached. Every line below is a bug that already cost time on 2026-07-26 — see SKILL.md.
#
#   bash launch-sharded.sh <harness.py> <workdir> "<extra harness args>"
#
# The harness must accept `--comfy <url> --shard N --of M` and SKIP work already on disk,
# so a relaunch resumes instead of redoing.
set -u
HARNESS="${1:?harness script}"; WORKDIR="${2:?work dir}"; EXTRA="${3:-}"
COMFY_DIR="${COMFY_DIR:-/workspace/ComfyUI}"
NGPU=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)
# HTTP via python3: the pod image ships without curl, so a curl-based queue clear
# silently did nothing and a curl-based readiness loop could never see a 200.
comfy_post(){ python3 -c 'import sys,urllib.request as u; u.urlopen(u.Request(sys.argv[1], data=sys.argv[2].encode(), headers={"Content-Type": "application/json"}), timeout=5)' "$1" "$2" >/dev/null 2>&1; }
comfy_up(){ python3 -c 'import sys,urllib.request as u; sys.exit(0 if u.urlopen(sys.argv[1], timeout=5).status == 200 else 1)' "$1" >/dev/null 2>&1; }

# 1. Kill the old instances FIRST. The pattern is a regex that survives flag changes:
#    a literal 'main.py --listen' stopped matching the moment --disable-cuda-malloc was
#    inserted before --listen, and the next launch would have doubled up on live GPUs.
#    Verify with `pgrep -af` before trusting any pkill.
# Match the PYTHON invocation, not the bare filename. `pkill -f gen-refflash2.py` also
# matches THIS launcher, whose own argv contains the harness path — so the script killed
# itself before starting anything and exited silently, no output, no error (2026-07-26).
pkill -f "python3 -u .*$(basename "$HARNESS")" 2>/dev/null
# ComfyUI queues SERVER-SIDE. Killing the harness does not cancel submitted prompts, so a
# relaunch with changed parameters (resolution, steps, model) silently produces frames at
# the OLD settings until the stale queue drains — and the new run just waits behind them.
# Clear + interrupt BEFORE killing the servers, while they can still answer (2026-07-26).
for g in $(seq 0 $((NGPU-1))); do
  comfy_post "http://127.0.0.1:$((8188+g))/queue" '{"clear":true}'
  comfy_post "http://127.0.0.1:$((8188+g))/interrupt" '{}'
done
pkill -f 'main\.py.*--listen' 2>/dev/null
sleep 8

# 2. Hold the lock BEFORE any long work, so the idle watchdog cannot stop the pod.
touch /workspace/.busy

# 3. --disable-cuda-malloc: the cudaMallocAsync pool retains freed blocks, and ComfyUI
#    reads free VRAM ONCE at model-load time to decide whether a model fits. With the
#    async allocator one GPU reported ~11GB less free than its identical twin and loaded
#    FLUX.2 partially (494 s/frame vs 127 s/frame, no error, both at 100% util).
cd "$COMFY_DIR"
for g in $(seq 0 $((NGPU-1))); do
  CUDA_VISIBLE_DEVICES=$g nohup setsid python main.py --disable-cuda-malloc \
    --listen 127.0.0.1 --port $((8188+g)) > /workspace/comfy_g$g.log 2>&1 </dev/null & disown
done

# 4. Wait for HTTP 200, not for a sleep. /workspace is MooseFS; boot can take minutes.
for g in $(seq 0 $((NGPU-1))); do
  pt=$((8188+g)); ok=0
  for i in $(seq 1 90); do
    comfy_up "http://127.0.0.1:$pt/system_stats" && { echo "comfy $pt READY"; ok=1; break; }
    sleep 10
  done
  [ "$ok" = 1 ] || { echo "FATAL: comfy $pt never came up"; rm -f /workspace/.busy; exit 1; }
done

# 5. python3 -u — block-buffered stdout made a live job look dead for 8 minutes once.
cd "$WORKDIR"
for g in $(seq 0 $((NGPU-1))); do
  nohup setsid python3 -u "$HARNESS" --comfy "http://127.0.0.1:$((8188+g))" \
    --shard $g --of $NGPU $EXTRA > "$WORKDIR/shard$g.log" 2>&1 </dev/null & disown
done

# 6. Sleep BEFORE the wait loop. `setsid … & disown` children are not visible to pgrep
#    immediately; without this the loop exits at once, prints DONE, and drops .busy while
#    the whole batch is still queued — handing a busy pod to the idle watchdog.
sleep 90
# SAME self-match trap as the kill above, and worse here: a bare `pgrep -f <harness>.py`
# matches THIS launcher's own argv, so the condition is permanently true — the launcher
# spins forever, never releases .busy, and never runs whatever was chained after it. It
# looks alive, which is why it went unnoticed while the job it was "waiting" on was dead.
# Refresh the lock every pass: autostop treats .busy as a HEARTBEAT and ignores it once
# older than --lock-ttl-min, and it only polls GPU0's queue, so a batch that outlives the
# TTL after shard 0 finishes would otherwise be stopped mid-run.
while pgrep -f "python3 -u .*$(basename "$HARNESS")" >/dev/null; do touch /workspace/.busy; sleep 30; done

rm -f /workspace/.busy
echo SHARDED_RUN_DONE
