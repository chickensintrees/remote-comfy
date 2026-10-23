# Playbook: the canonical run

Run every command from the repo root. `R=$(pwd)` is assumed; on the pod, scripts live
in `/workspace`.

## The verdict that keeps getting re-derived wrong

**Plain pods work.** An early verdict that "hand-managed pods are the wrong tool, use
managed inference" was disproven (see
[`decisions/2026-07-25-plain-pods-not-serverless.md`](../decisions/2026-07-25-plain-pods-not-serverless.md)).
What failed was the **serverless / custom-Docker** path. On a plain pod,
`LoadWanVideoT5TextEncoder` (the node that "does not exist" on serverless) is present,
along with all 116 WanVideo nodes, after a plain `git clone`. Managed fal/Replicate
endpoints are stopgaps: they cannot run a custom graph.

## 0. STEP ZERO: what models exist today?

```bash
python remote_comfy/check_latest_models.py --search flux    # or qwen / wan / any family
python remote_comfy/check_latest_models.py                  # newest across the usual orgs
```

For each candidate check: **licence** (open weights vs API-only), **file size / VRAM**
(`https://huggingface.co/api/models/<repo>?blobs=true`), **native ComfyUI node support**,
and whether a **Turbo/distilled LoRA** exists (decisive for large batches). Newest is not
always best, but not knowing what exists is never acceptable. The concrete miss that
created this rule: a 3-way bake-off on FLUX.1-era models while FLUX.2 (Nov 2025) already
shipped native multi-reference.

## 1. Account prerequisites (once)

- `RUNPOD_API_KEY` in your env, or `python -m keyring set remote-comfy runpod`.
- Your SSH public key in RunPod → Settings → **SSH Public Keys**. Keys are injected at pod
  **boot**; one added later never works on an existing pod.

## 2. Budget, stock, create

```bash
python remote_comfy/pod_ctl.py balance                  # what can you actually afford?
python remote_comfy/pod_ctl.py list                     # is anything else already billing?
python remote_comfy/pod_ctl.py availability --min-vram 48
python remote_comfy/pod_ctl.py create --name work --gpu "NVIDIA A40" --gpu-count 8 \
    --container-gb 30 --volume-gb 200 --ports "8188/http,22/tcp"
python remote_comfy/pod_ctl.py conn <podId>             # ALWAYS re-read ip/port
```

`create` wants a `gpuTypeId` (`"NVIDIA GeForce RTX 4090"`); `availability` prints a
`displayName` (`"RTX 4090"`). A 500 from `create` means no capacity: try the next GPU in
cost order. Use pod-local `--volume-gb`, not a network volume (they DC-lock you).
Immediately after create, `ssh … uptime`: a fresh pod on a saturated host (load 28+) is
a bad draw, so terminate and redraw.

## 3. Push scripts, provision, start the cost guard

```bash
scp -P <port> pod/*.sh remote_comfy/autostop.py remote_comfy/comfy_client.py root@<ip>:/workspace/
ssh -p <port> root@<ip> 'nohup setsid bash /workspace/provision-comfyui.sh flux2 \
    > /workspace/prov.log 2>&1 </dev/null & disown'
ssh -p <port> root@<ip> "RUNPOD_API_KEY=$RUNPOD_API_KEY nohup setsid python3 /workspace/autostop.py \
    --pod-id <podId> --idle-min 90 --outputs-root /workspace/out \
    > /workspace/autostop.log 2>&1 </dev/null & disown"
```

Use **direct-TCP SSH** (the IP + port from `conn`), not RunPod's SSH proxy: the proxy is
PTY-only, so `scp`, `-L` and non-interactive commands fail. Model sets: `wan`, `qwen`,
`flux`, `flux2`, `kontext`, `3d`, `none` (space-separated for several).

Watch `prov.log` for `PROVISION_DONE` **and** grep for `PROVISION_FAILED` and `MISS`.
Then confirm models on disk by size, not by the marker.

### The cost guard

`autostop.py` runs **on the pod** and stops the pod itself, so an abandoned pod still
dies after the laptop sleeps or the agent session ends.

- idle = ComfyUI `/queue` empty (running AND pending) continuously for `--idle-min`
- `--max-hours` is a hard ceiling. Treat it as the budget, not a formality.
- unreachable ComfyUI counts as BUSY (never kill a booting pod)
- `/workspace/.busy` holds the pod **only while fresh** (`--lock-ttl-min`, default 20).
  Wrap long non-ComfyUI work: `bash /workspace/hold-busy.sh -- <cmd>`.
- before retiring a pod it checks GPU stock: High → stop (restartable); Low + outputs
  synced → terminate; Low + unsynced → refuse both and keep billing rather than lose work.
- `--outputs-root` makes the synced check per-directory; without it the check logs `[WEAK]`.
- During an active session keep `--idle-min` high (90+). Auto-stop is for *forgotten*
  pods, not for pausing between steps.

## 4. Drive it

```bash
ssh -N -L 8189:localhost:8188 -p <port> root@<ip> &     # then http://127.0.0.1:8189
#   or, no tunnel (GET only, small payloads): https://<podId>-8188.proxy.runpod.net
```

```python
from remote_comfy.comfy_client import Comfy
c = Comfy("http://127.0.0.1:8189"); c.wait_ready()
outs = c.run(workflow_api_dict)          # -> [(filename, bytes), ...]
```

For batches, run the harness **on the pod** against `localhost` and ship back only
results: the proxy chokes on bulk payloads and the tunnel adds latency per call.

## 5. Batch across every GPU

```bash
ssh -p <port> root@<ip> 'mkdir -p /workspace/job'
scp -r -P <port> examples/batch_harness.py examples/jobs.json examples/workflows root@<ip>:/workspace/job/
ssh -p <port> root@<ip> 'nohup setsid bash /workspace/launch-sharded.sh \
    /workspace/job/batch_harness.py /workspace/job "--jobs /workspace/job/jobs.json --out /workspace/out" \
    > /workspace/launch.log 2>&1 </dev/null & disown'
bash pod/check-gpu-load.sh <ip> <port>                   # fails on "loaded partially"
bash local/sync-outputs.sh <ip> <port> /workspace/out ./out &
```

The harness contract: accept `--comfy <url> --shard N --of M`, and **skip work already on
disk** so a relaunch resumes. Use `python3 -u`. Time the first 3–5 items before
projecting the batch (estimates have been off by 2–5x).

## 6. Pause or finish

```bash
python remote_comfy/pod_ctl.py stop <podId>        # GPU metering stops; volume billed
python remote_comfy/pod_ctl.py start <podId>       # then: conn again, re-run provision deps
python remote_comfy/pod_ctl.py terminate <podId>   # destroys pod-local disk; confirms first
```

After a resume only `/workspace` survives. Re-run `provision-comfyui.sh none` (idempotent;
reinstalls deps, skips models). Stopping can strand a pod whose GPU type has low stock.
Pause only on High-stock GPUs, and never with unsynced outputs.
