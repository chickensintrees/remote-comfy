# Plain pods, not serverless or custom Docker

**Context.** On 2026-07-19 the toolkit concluded that "hand-managed pods are the wrong
tool; use managed inference". For six days that verdict steered work toward fal/Replicate
and a custom RunPod serverless worker built on `runpod/worker-comfyui`.

**What actually failed.** The *serverless / custom-Docker* path: the worker image lacked
WanVideoWrapper's `LoadWanVideoT5TextEncoder`, so the graph could not run. Neither RunPod
nor WanVideoWrapper was at fault.

**Decision (2026-07-25).** Use **plain pods**: stock `runpod/pytorch` image, `git clone`
ComfyUI and custom nodes, provision with `pod/provision-comfyui.sh`. On a plain pod all
116 WanVideo nodes, including `LoadWanVideoT5TextEncoder`, are present.

**Rejected.** Managed i2v endpoints (fal, Replicate) cannot run a custom graph, so they
are stopgaps only. Managed ComfyUI hosts (RunComfy, Comfy.ICU) cost 6–25x more for a
saturated batch; Comfy.ICU also forbids custom-node installs. See `docs/gpu-choice.md`.

**Would change it.** A serverless worker that accepts arbitrary custom nodes at
plain-pod prices, or a workload that is bursty enough that per-second billing wins.
