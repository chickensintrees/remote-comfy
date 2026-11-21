---
name: remote-comfy
description: Rent a GPU on RunPod, run ComfyUI on it, and drive it from the laptop, for any batch image/video/audio generation that outgrows the local card. Holds the verified plain-pod playbook, the on-pod auto-stop cost guard, GPU choice by throughput-per-dollar, and ~50 traps that cost real time (SSH port remaps on resume, network volumes DC-lock you, serverless is not pods). Also drives Comfy Cloud with the same client. Triggers: ComfyUI, RunPod, Comfy Cloud, remote GPU, WanVideo, FLUX, i2v, batch render, pod, GPU cloud, "run it on a bigger GPU".
---

# remote-comfy

Tools and docs live in the **remote-comfy repo checkout**. Resolve it once:

```bash
RC="${REMOTE_COMFY_HOME:-$HOME/remote-comfy}"   # set REMOTE_COMFY_HOME to your clone
test -f "$RC/AGENTS.md" || echo "set REMOTE_COMFY_HOME to your remote-comfy clone"
```

**Then read `$RC/AGENTS.md`**: it has the hard rules, layout and commands. The
step-by-step run is `$RC/docs/playbook.md`; the traps are `$RC/docs/traps.md`.

## Non-negotiables (full detail in AGENTS.md)

1. **STEP ZERO:** `python "$RC/remote_comfy/check_latest_models.py" --search <family>`
   before choosing any model. Your training data is stale.
2. `python "$RC/remote_comfy/pod_ctl.py" balance` and `availability` **before** `create`.
3. Start `autostop.py` on every pod. Hold long work with `hold-busy.sh -- <cmd>`.
4. Run `local/sync-outputs.sh` alongside every batch: pod storage is scratch.
5. `pod_ctl.py conn <podId>` after every resume; the SSH port remaps.
6. After changing the toolkit: `python "$RC/tests/test_runpod_ops.py"` must print ALL PASS.

Short jobs on common models can skip the pod: Comfy Cloud via `connect("cloud")` or
`batch_harness.py --comfy cloud` (playbook section 7; no TRELLIS.2, so not for 3D).
