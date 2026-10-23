# Architecture: what runs where

```
 LAPTOP                                          POD  (RunPod, /workspace = persistent volume)
 ──────                                          ───
 pod_ctl.py  ──REST/GraphQL──▶ RunPod API ◀──────── autostop.py   (stops/terminates ITSELF)
                                                       │  polls
 comfy_client.py ──ssh -L 8189:8188──────────────▶ ComfyUI :8188 (+ :8189… one per GPU)
                                                       ▲
                                                 launch-sharded.sh ─▶ harness × N GPUs
                                                 hold-busy.sh ─▶ /workspace/.busy (heartbeat)
 sync-outputs.sh ◀──ssh + tar stream──────────── /workspace/out/**
      └─ touches /workspace/.synced.d/<slug> ──▶ read by autostop before any terminate
 check-gpu-load.sh ──ssh──▶ greps comfy_g*.log for "loaded partially"
```

## Why each piece lives where it does

- **The watchdog is on the pod**, not the laptop: a laptop watchdog dies with the laptop,
  the session, or the agent, and a forgotten pod bills around the clock.
- **The batch harness is on the pod**, not the laptop: the RunPod HTTP proxy times out on
  multi-MB payloads (`/object_info`) and gates writes. The laptop only controls and pulls.
- **Sync is driven from the laptop**, because the laptop is the only place an artifact is
  safe. The sync loop writes a **per-directory** sentinel on the pod so the watchdog can
  tell "these outputs are home" from "some loop is running somewhere".
- **The busy lock is a heartbeat**, refreshed by `hold-busy.sh`, and ignored once stale.
  A plain flag file outlived its job and held an idle H100 for 3 hours.

## State on the pod

| path | owner | meaning |
|---|---|---|
| `/workspace/ComfyUI` | provision | ComfyUI + custom nodes + models (survives stop/start) |
| `/workspace/.busy` | hold-busy / provision / launcher | fresh mtime = "don't stop me" |
| `/workspace/.synced.d/<slug>` | sync-outputs | that remote dir was fully verified locally at mtime |
| `/workspace/comfy.log`, `comfy_g<N>.log` | ComfyUI | per-instance logs; `check-gpu-load.sh` reads these |
| container disk (pip, apt) | — | **discarded on every stop/start** |

## Dependencies

Laptop: Python 3.9+, `ssh`/`scp`, `bash` (Git Bash on Windows). Optional `keyring`.
Pod: the stock `runpod/pytorch` image. Pod scripts use only `python3`, `bash`, `tar`,
`git`, and `pip`, with no `curl`, `tmux`, or system `ffmpeg` assumed.
