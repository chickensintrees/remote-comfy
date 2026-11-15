# examples

`batch_harness.py` is the shard-aware harness `pod/launch-sharded.sh` expects
(`--comfy URL --shard N --of M`, skip work already on disk). A job list is a JSON list of
`{"id", "workflow", "set": {"<node>.<input>": value}}`; each job overrides inputs on a
copy of its graph.

The graphs in `workflows/` are in ComfyUI's API format. Each runs on a pod provisioned
with the model set named here, and the tests check that every model file a graph loads is
downloaded by that set.

| Use case | Graph | Job list | Model set |
|---|---|---|---|
| A batch of images | `flux2_dev_txt2img.json` | `jobs_batch.json` (24 prompts) | `flux2` |
| Editing an image | `qwen_image_edit_2511.json` | `jobs_edit.json` (5 edits) | `qwen` |
| Image to video | `wan22_i2v_14b.json` | `jobs_i2v.json` (4 clips) | `wan` |
| Cutouts and depth | `cutout_birefnet.json`, `depth_moge.json` | `jobs_cutout_depth.json` | `3d` |
| Image to 3D | `image_to_3d.json` | none: see below | `3d` |
| A minimal graph | `flux1_dev_txt2img.json` | `jobs.json` (3 prompts) | `flux` |

All of these except the minimal graph ran on one L40S on 2026-11-15, with the timings and
costs in `decisions/2026-11-15-use-cases-run.md`. The minimal graph ran on 2x A40 on
2026-10-23 (`decisions/2026-10-23-live-smoke-test.md`).

The image, edit, video and 3D graphs follow Comfy-Org's official templates
(`workflow_templates/templates/`: `image_flux2_fp8`, `image_qwen_image_edit_2511`,
`video_wan2_2_14B_i2v`, `3d_pixal3d_trellis2_image_to_model`), flattened out of their
subgraphs. `image_to_3d.json` holds both 3D models behind a switch node: set the
`PrimitiveBoolean` `value` to `true` for TRELLIS.2 and `false` for Pixal3D.

Graphs that read an image (`LoadImage`) expect it in `ComfyUI/input/` on the pod; copy
it there first. The video graph needs `--wait-min 60`, because a clip takes about
8 minutes on one L40S.

Run STEP ZERO before you copy a graph: these are examples, not recommendations. Export
your own graphs with ComfyUI's *Save (API format)*.

```bash
# on the pod, after provision-comfyui.sh flux2:
bash /workspace/launch-sharded.sh /workspace/job/batch_harness.py /workspace/job \
    "--jobs /workspace/job/jobs_batch.json --out /workspace/out"
```
