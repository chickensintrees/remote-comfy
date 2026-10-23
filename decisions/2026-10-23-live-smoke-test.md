# First live smoke test of the public harness

**What ran.** 2x A40 (L4 and A5000 had no capacity; the create loop fell through in cost
order), `provision-comfyui.sh flux`, `autostop.py --idle-min 10 --outputs-root
/workspace/out`, `launch-sharded.sh` with `examples/batch_harness.py`, and
`local/sync-outputs.sh` from the laptop. Total spend about $0.85.

**Worked.** Provision in 4.8 min with the torch trio agreeing (2.14.0+cu126) and all
model files verified on disk. Both per-GPU ComfyUI instances reached READY via the
python readiness helper. Three FLUX.1-dev images rendered across both GPUs (shard 0 got
two jobs, shard 1 one; ~60 s cold, ~18 s warm, 1.18/1.25 it/s) and reached the laptop
within 153 s of launch. The sync loop exited on its own once the host was gone.

**Broke, and fixed the same day** (each now has a regression test that fails on the old
code):
1. `check-gpu-load.sh` could never pass: ComfyUI 0.42.0 no longer prints
   `loaded completely/partially`. Rewritten around sampling-speed parity.
2. The watchdog's REST calls lacked a browser User-Agent (403), a failed terminate was
   swallowed, and `main()` exited, leaving the pod billing unguarded. Terminated by hand.
3. Flat output directories were never checked, and the sync sentinel name never matched.

**Re-verified.** A 1x L4 pod with a stand-in ComfyUI (empty queue), `--idle-min 1`: the
fixed watchdog removed the pod from the account by itself about a minute after idling.

**Observed, not a bug.** `runpod/pytorch:2.4.0-py3.11-cuda12.4.1` ships `curl`; the
traps table had said pods never do. `/workspace` was MooseFS even with a pod-local
volume. All visible stock was "Low".

**Would change it.** A run against a pod holding real unsynced output under
`--outputs-root`, to watch the refuse-to-terminate branch live.
