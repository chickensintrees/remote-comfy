# Five use cases on one L40S

**Context.** The project page showed only still images from one project. The goal was a set
of examples that shows what the toolkit is for: one job each for a batch of images, image
edits, image to video, image to 3D, and cutouts and depth, each with its measured time and
cost.

**What ran.** 1x L40S 48 GB at $1.09/hr, `provision-comfyui.sh flux2 qwen wan 3d`,
`autostop.py --idle-min 30 --max-hours 5 --outputs-root /workspace/out`, `launch-sharded.sh`
with `examples/batch_harness.py` and the job lists in `examples/`, the image-to-3D runner
(template converted against the pod's own `/object_info`), and `local/sync-outputs.sh` from
the laptop. ComfyUI at commit `258f880` (2026-11-15). 40 jobs, 0 failures, 1.9 hours, $2.03
in total, read back from the account balance.

| Step | Model | Jobs | Measured |
|---|---|---|---|
| Provision four sets | | 18 files, 138 GB | 20 min (downloads at about 200 MB/s) |
| A batch of images | FLUX.2 [dev], 20 steps, 1536x1024 | 24 | 45 s each warm, 208 s cold; 21 min |
| Editing an image | Qwen-Image-Edit 2511, 40 steps | 5 | 102 s each warm, 201 s cold |
| Cutouts and depth | BiRefNet; MoGe 2 | 3 | 9 s; 3-15 s |
| Image to video | Wan 2.2 I2V A14B, 20 steps, 832x560, 81 frames | 4 | about 475 s each warm, 556 s cold |
| Image to 3D | TRELLIS.2 / Pixal3D bf16, 60k faces | 4 | about 167 s warm, 534 s cold; Pixal3D 178 s |

**Decided.**
1. Two L40S were the plan, so the batch would show the split across GPUs. No 48 GB Ada card
   was available in pairs (L40S, RTX 6000 Ada, L40), so the run used one. Two H100s would
   have cost about 4x as much. Blackwell cards (RTX PRO 6000) were ruled out because the
   provisioner pins torch for CUDA 12.6.
2. The `qwen` set now installs Qwen-Image-Edit 2511 (Apache-2.0) in place of the original
   2025 release, which the catalogue no longer recommends.
3. The graphs were flattened by hand from the official templates, because the templates
   wrap their graphs in subgraphs. They were checked before renting against a local
   ComfyUI's `/object_info` and its own `/prompt` validation. That check caught seven
   errors in the depth graph.

**Learned, now enforced.**
- A graph can name a model file no provision set downloads (the 3D template defaults to
  int8 weights; the `3d` set ships bf16). A test now checks every example graph against
  the provisioner, and every job list's overrides against its graph.
- The docs said to clone quietly, but `provision-comfyui.sh` did not, so ComfyUI's clone
  filled `prov.log` with about 1,300 progress updates. A test now checks every clone line.
- `uptime` load is relative to the core count: a 256-core host at load 30-40 was about 15%
  busy and ran well. `docs/traps.md` now says so.

**Would change it.** Two L40S in stock (the batch then shows the split). A network volume
holding these four sets, if runs become frequent: here provisioning cost about $0.36 of the
$2.03.
