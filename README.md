# remote-comfy

Rent a GPU on [RunPod](https://www.runpod.io), run [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
on it, and drive it from your laptop, **without leaving a pod billing overnight or losing
a batch when the pod disappears.**

It is a small, stdlib-only toolkit plus an operating playbook written for both humans and
coding agents (Claude Code, Codex, etc.). Every rule in it came from a real failure on a
live pod, and most are enforced by an executable test rather than prose.

## What you get

- **`pod_ctl.py`**: create/list/stop/start/terminate pods, check balance and per-DC GPU
  stock, and resolve the *current* SSH endpoint (it changes on every resume).
- **`autostop.py`**: a watchdog that runs *on the pod* and shuts the pod down when
  ComfyUI goes idle, so it still works after your laptop sleeps. It is stock-aware: it
  will not strand a pod whose GPU is scarce, nor destroy one holding unsynced outputs.
- **`provision-comfyui.sh`**: installs ComfyUI, custom nodes and model sets (Wan 2.2,
  FLUX.1/FLUX.2, Qwen-Image-Edit, Kontext, TRELLIS.2/Pixal3D) in the only order that
  survives torch/CUDA re-resolution, and fails loudly on any missing file.
- **`launch-sharded.sh`**: one ComfyUI per GPU, batch sharded across them.
- **`sync-outputs.sh`**: continuously pulls results to your machine and tells the
  watchdog which directories are safe.
- **`comfy_client.py`**: a tiny client that drives a local or remote ComfyUI the same way.
- **`docs/traps.md`**: ~50 traps (SSH port remaps, network volumes DC-locking you, torch
  trio mismatches, VRAM squatters halving throughput…) each with the rule that avoids it.

## Quickstart

```bash
git clone https://github.com/chickensintrees/remote-comfy && cd remote-comfy
export RUNPOD_API_KEY=...                      # or: python -m keyring set remote-comfy runpod
python tests/test_runpod_ops.py                # offline; should print ALL PASS
python remote_comfy/pod_ctl.py balance
python remote_comfy/pod_ctl.py availability --min-vram 24
```

Add your SSH public key in RunPod → Settings → SSH Public Keys **before** creating a pod.
Then follow [`docs/playbook.md`](docs/playbook.md) end to end.

> ⚠️ **This rents real hardware with real money.** Read the cost-guard section of the
> playbook and run `autostop.py` on every pod. You are responsible for your RunPod bill.

## For coding agents

Start at [`AGENTS.md`](AGENTS.md). To make it a Claude Code skill available in every
project:

```bash
bash scripts/install-skill.sh
export REMOTE_COMFY_HOME="$PWD"
```

## Layout

```
AGENTS.md            rules + layout + commands (agents start here)
remote_comfy/        laptop-side Python tools (autostop.py is copied to the pod)
pod/                 scripts that run ON the pod
local/               scripts that run on your machine against the pod
docs/                playbook, traps, architecture, GPU choice, open questions
decisions/           dated records of why X over Y
examples/            shard-aware batch harness + a minimal workflow
skills/remote-comfy/ Claude Code skill
tests/               offline tripwires; CI runs them on every push
```

## Requirements

Python 3.9+, `ssh`/`scp`, and `bash` (Git Bash works on Windows). Optional: `keyring`
for storing the API key, `pillow` + `numpy` for `comfy_client.mean_luma`.

## Contributing

Learned a new trap? Add an assertion to `tests/test_runpod_ops.py` first, then the row in
`docs/traps.md`. See [`AGENTS.md`](AGENTS.md#working-on-this-repo).

## License

[MIT](LICENSE). Not affiliated with RunPod or ComfyUI.
