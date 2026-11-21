# remote-comfy

![A batch of 24 images rendered with FLUX.2 [dev] on one rented L40S](site/media/uc/hero.jpg)

remote-comfy is a toolkit for renting a GPU on [RunPod](https://www.runpod.io), running
[ComfyUI](https://github.com/comfyanonymous/ComfyUI) on it, and driving it from your laptop.
A watchdog on the pod shuts it down when the work stops, so a forgotten pod does not bill
overnight, and a sync loop copies every result to your machine as it lands. Short jobs can
run on [Comfy Cloud](#comfy-cloud) instead, with the same client and no pod.

It is a set of small Python and shell tools, a step-by-step playbook, and a Claude Code
skill. It is written for coding agents such as Claude Code and Codex, and every step also
works by hand. The project page is [billmoore.ai/remote-comfy](https://billmoore.ai/remote-comfy/).

## Set it up

The quickest way is to paste this line into Claude Code:

```text
Set up remote-comfy with me by following https://billmoore.ai/remote-comfy/install.md
```

Claude clones this repository, runs the offline checks, installs the skill, and helps you
store your RunPod API key. It asks before it changes anything outside the cloned folder,
and setup rents nothing. You type the API key into your own terminal, so it never passes
through the chat.

To set it up by hand:

```bash
git clone https://github.com/chickensintrees/remote-comfy && cd remote-comfy
python tests/test_runpod_ops.py                # offline; the last line should be ALL PASS
pip install keyring                            # optional, to keep the key in the OS keyring
python -m keyring set remote-comfy runpod      # paste your RunPod API key when it asks
python remote_comfy/pod_ctl.py balance         # read-only; confirms the key works
```

If you would rather not use the keyring, set `RUNPOD_API_KEY` in your shell profile.
Add your SSH public key in RunPod under Settings, SSH Public Keys, before you create your
first pod, because RunPod adds keys to a pod only when it boots.

To make the skill available to Claude Code in every project, run
`bash scripts/install-skill.sh` and add the `REMOTE_COMFY_HOME` line it prints to your
shell profile.

You need Python 3.9 or newer, `ssh` and `scp`, and `bash`. On Windows, Git Bash works.
The tools use only the Python standard library, because a fresh pod has a bare Python.

## How it works

A batch runs on the pod, next to the GPUs. Your machine rents the pod, starts the work
and pulls the results home.

1. `pod_ctl.py` reads your balance and which GPUs are in stock, then creates a pod on the
   cheapest GPU that fits the job.
2. `provision-comfyui.sh` installs ComfyUI, its custom nodes and the models on the pod,
   and stops with an error if any file is missing.
3. `launch-sharded.sh` starts one ComfyUI per GPU and splits the batch across them.
4. `sync-outputs.sh` copies each result to your machine as soon as it lands, and marks a
   folder as safe once every file in it has arrived.
5. `autostop.py` runs on the pod the whole time and retires the pod when ComfyUI goes idle.

[`docs/playbook.md`](docs/playbook.md) walks through a full run with every command, and
[`docs/architecture.md`](docs/architecture.md) shows what runs where.

### The cost guard

The watchdog runs on the pod, so it keeps working after your laptop sleeps or the agent
session ends. Before it retires an idle pod, it checks whether the GPU type is in stock and
whether every output folder has reached your machine.

| When | The watchdog |
|---|---|
| ComfyUI has work queued, has not started yet, or a long job holds the busy lock. | It waits. |
| ComfyUI has been idle for `--idle-min`, and the GPU type has high stock. | It stops the pod, which can be started again later. |
| The pod is idle, stock is low, and every output folder has been synced. | It terminates the pod. |
| The pod is idle, stock is low, and an output folder has not been synced. | It keeps billing rather than destroy work that exists only on the pod. |
| The pod has run for `--max-hours`, which is 12 by default. | It retires the pod by the same rules. |

## Tools

| Tool | Runs on | What it does |
|---|---|---|
| `remote_comfy/pod_ctl.py` | your machine | It creates, lists, stops, starts and terminates pods, shows your balance and GPU stock, and prints the pod's current SSH address, which changes on every restart. |
| `remote_comfy/check_latest_models.py` | your machine | It lists the newest models on Hugging Face, so you choose from what exists today. |
| `remote_comfy/catalog.py` | your machine | It lists current open models by task with the files ComfyUI loads, and checks the catalogue against Hugging Face again. |
| `remote_comfy/autostop.py` | pod | It is the watchdog that stops or terminates the pod when ComfyUI goes idle. |
| `pod/provision-comfyui.sh` | pod | It installs ComfyUI, custom nodes and model sets (`wan`, `qwen`, `flux`, `flux2`, `kontext`, `3d`) in an order that keeps torch and CUDA consistent. |
| `pod/launch-sharded.sh` | pod | It starts one ComfyUI per GPU and splits a batch across them. |
| `pod/hold-busy.sh` | pod | It keeps the pod awake while a long job that is not ComfyUI runs, and lets go when the job ends. |
| `local/sync-outputs.sh` | your machine | It pulls results home while a batch runs, checks every file, and tells the watchdog which folders are safe. |
| `pod/check-gpu-load.sh` | your machine, over SSH | It fails when one GPU samples much slower than the others, which usually means a model did not fit. |
| `remote_comfy/comfy_client.py` | either | It drives a local or a remote ComfyUI in the same way, and Comfy Cloud with the same calls. |

## Choosing a GPU and a model

You pay for GPU-hours, so eight GPUs cost the same as one for the same work and finish
sooner. [`docs/gpu-choice.md`](docs/gpu-choice.md) compares configurations by work per
dollar, and `pod_ctl.py availability --min-vram <GB>` shows today's stock and prices.

[`docs/models.md`](docs/models.md) lists current open models for image, video, 3D, speech,
music and utilities, with each one's licence, VRAM and the exact files ComfyUI loads. New
models ship every month, so run `check_latest_models.py` and `catalog.py --verify` before
you commit to a batch.

## Comfy Cloud

[Comfy Cloud](https://docs.comfy.org/development/cloud/overview) runs the same graphs on Comfy's own GPUs and bills
only while a job runs, so there is no pod to set up or forget. `connect("cloud")` in
`comfy_client.py` and `batch_harness.py --comfy cloud` use it, with the key in
`COMFY_CLOUD_API_KEY` or the keyring. It needs a paid Comfy plan, has only the most-used
custom nodes, and limits each run to 30 minutes (1 hour on Pro). On 20 November 2026 it
had every node and model for six of the seven example graphs; image to 3D lacks the
TRELLIS.2 weights. Use a pod for long batches and anything it lacks. Setup is in
[`docs/playbook.md`](docs/playbook.md#7-or-skip-the-pod-comfy-cloud).

## Traps

[`docs/traps.md`](docs/traps.md) lists the traps that cost time or money on a live pod,
each with the rule that avoids it. Most are also an offline check in
`tests/test_runpod_ops.py`. Read the list once before your first pod, and search it
whenever something looks like a hardware fault or a hung boot.

## Examples

The [project page](https://billmoore.ai/remote-comfy/#examples) shows five use cases from
one live run, each with its time and cost: a batch of images, image edits, image to video,
image to 3D, and cutouts and depth. [`examples/`](examples/) holds the graph and job list
for each, and the shard-aware batch harness that runs them.

## Status and limits

- This is version 0.1. The full run was last tested live on 15 November 2026: setup and
  40 jobs across five graphs on one L40S, in 1.9 hours, for $2.03
  ([record](decisions/2026-11-15-use-cases-run.md)).
- The offline checks run in CI on Python 3.9 and 3.12 on every push. They need no
  network, GPU or API key.
- Pods are rented on RunPod only. The Comfy Cloud client ran live on 20 November 2026
  (a background-removal job through the batch harness); its cost per job has not been
  measured yet ([record](decisions/2026-11-20-comfy-cloud-backend.md)).
- The watchdog reads the queue of the first ComfyUI only. The launcher keeps the pod busy
  while any GPU still has work.
- [`docs/open-questions.md`](docs/open-questions.md) lists what has not been proven yet.
- It rents real hardware with real money. Run `autostop.py` on every pod. You are
  responsible for your RunPod bill.

## For coding agents

Agents start at [`AGENTS.md`](AGENTS.md), which holds the rules, the layout and the
commands. The skill in `skills/remote-comfy/` points Claude Code at it.

## Layout

```text
AGENTS.md            rules, layout and commands (agents start here)
remote_comfy/        Python tools for your machine (autostop.py is copied to the pod)
pod/                 scripts that run on the pod
local/               scripts that run on your machine against the pod
catalog/             the model catalogue as JSON (docs/models.md is generated from it)
docs/                playbook, traps, architecture, GPU choice, models, open questions
decisions/           dated records of why one option was chosen over another
examples/            graphs and job lists for five use cases, and the batch harness
skills/remote-comfy/ the Claude Code skill
scripts/             the skill installer
site/                the project page (python site/build.py rebuilds it)
tests/               offline checks; CI runs them on every push
```

## Contributing

If you hit a new trap, add an assertion to `tests/test_runpod_ops.py` first, then add the
row to `docs/traps.md`. [`AGENTS.md`](AGENTS.md#working-on-this-repo) describes how to
work on the repository.

## License

[MIT](LICENSE). remote-comfy is not affiliated with RunPod or ComfyUI.
