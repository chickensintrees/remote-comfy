# AGENTS.md — remote-comfy

You are working in a harness for **renting a GPU on RunPod, running ComfyUI on it, and
driving it from a laptop**. Every rule here was paid for in pod time or money. Read this
file fully before you spend a GPU-minute.

## Orientation (read in this order)

1. **This file** — rules, layout, commands.
2. [`docs/playbook.md`](docs/playbook.md) — the canonical run, step by step.
3. [`docs/traps.md`](docs/traps.md) — ~50 traps, each with the rule that avoids it.
   Skim it before your first pod; search it whenever something "looks like" a hardware
   fault or a hung boot.
4. [`docs/architecture.md`](docs/architecture.md) — what runs where (laptop vs pod).
5. [`docs/gpu-choice.md`](docs/gpu-choice.md) and
   [`docs/open-questions.md`](docs/open-questions.md) when choosing hardware or quoting
   a number. Open questions are **not** settled facts.
6. [`decisions/`](decisions/) — dated records of why X over Y. Check here before
   re-litigating a design choice.

## Layout

| path | runs on | what |
|---|---|---|
| `remote_comfy/pod_ctl.py` | laptop | RunPod control: `list`, `status`, `balance`, `availability`, `create`, `conn`, `stop`, `start`, `terminate` |
| `remote_comfy/comfy_client.py` | either | stdlib ComfyUI client: `Comfy(url).wait_ready() / upload() / run()` |
| `remote_comfy/check_latest_models.py` | laptop | STEP ZERO: what models exist *now* (live HF API) |
| `remote_comfy/autostop.py` | **pod** | idle watchdog that stops/terminates the pod itself |
| `pod/provision-comfyui.sh` | **pod** | install ComfyUI + nodes + models in the only order that works |
| `pod/launch-sharded.sh` | **pod** | one ComfyUI per GPU, shard a batch harness across them |
| `pod/hold-busy.sh` | **pod** | keep the watchdog's busy-lock fresh while a job runs |
| `pod/check-gpu-load.sh` | laptop → pod | fail if any GPU loaded its model only *partially* |
| `local/sync-outputs.sh` | laptop | pull outputs back continuously while a batch runs |
| `skills/remote-comfy/SKILL.md` | — | Claude Code skill; install with `scripts/install-skill.sh` |
| `examples/` | — | a shard-aware batch harness and a minimal workflow |
| `tests/test_runpod_ops.py` | laptop/CI | the tripwires (no network, no GPU, no key) |

## Hard rules

1. **STEP ZERO: research current models first.** Run
   `python remote_comfy/check_latest_models.py --search <family>` before choosing a
   model or designing a test. Your training data is stale. (A full bake-off was once run
   on FLUX.1-era models while FLUX.2 already shipped the exact capability under test.)
2. **Never leave a pod billing.** Start `autostop.py` on every pod. Wrap long
   non-ComfyUI work in `pod/hold-busy.sh -- <cmd>`; never bare-`touch /workspace/.busy`.
3. **Pod storage is scratch.** Run `local/sync-outputs.sh` alongside every batch. If an
   artifact is not on the laptop, it does not exist.
4. **Re-read the connection after every resume** (`pod_ctl.py conn <podId>`). The SSH
   port remaps on every stop/start, and pip/apt installs are discarded.
5. **Check budget and stock before creating.** `pod_ctl.py balance` and
   `pod_ctl.py availability --min-vram <GB>`. A `create` 500 means no capacity.
6. **Measure before you project.** Time the first 3–5 real items under the final
   configuration before quoting a duration or a cost.
7. **Monitor artifacts, not done-markers.** Count/size files on disk; a script's own
   `DONE` line has printed over total failure more than once.
8. **Never put a secret on disk or in a URL.** `RUNPOD_API_KEY` goes in the pod's env
   and the laptop's env/keyring only. See `.env.example`.

## Commands

```bash
python tests/test_runpod_ops.py           # run after touching ANYTHING; must print ALL PASS
python remote_comfy/pod_ctl.py --help
bash scripts/install-skill.sh             # deploy the Claude Code skill to ~/.claude/skills
```

On Windows, `python3` may be the Microsoft Store stub (exits 49). Probe with
`python3 -c "print(1)" || python -c "print(1)"` and use whichever works.

## Working on this repo

- **test > hook > lint > doc > comment.** When you learn a lesson, add an assertion to
  `tests/test_runpod_ops.py` **first**, then the row in `docs/traps.md`. A lesson that
  lives only in prose rots into confident wrongness.
- Doc assertions search `AGENTS.md`, the skill, and `docs/*.md` together, so a trap may
  move between files but cannot silently disappear.
- A design choice with a real alternative gets a dated note in `decisions/`
  (`YYYY-MM-DD-slug.md`): context, decision, what was tried, what would change it.
- Pod-side scripts must not assume `curl`, `tmux`, `screen`, or system `ffmpeg` exist.
  Use `python3` for HTTP. Launch long jobs with `nohup setsid … & disown`.
- Keep the tools **stdlib-only** (the pod has a bare Python). `keyring`, `PIL`, `numpy`
  are optional imports.
- Nothing project- or person-specific belongs here: no pod IDs, volume IDs, private
  repo paths, or names. CI greps for leaked keys and absolute user paths.
