# examples

- `batch_harness.py`: the shard-aware harness contract `pod/launch-sharded.sh` expects
  (`--comfy URL --shard N --of M`, skip work already on disk).
- `jobs.json`: three jobs over one workflow, each overriding `<node>.<input>` values.
- `workflows/flux1_dev_txt2img.json`: API-format FLUX.1-dev txt2img using the
  all-in-one checkpoint from `provision-comfyui.sh flux` (`CheckpointLoaderSimple`
  outputs MODEL=0, CLIP=1, VAE=2).

Run STEP ZERO before copying this workflow: FLUX.1-dev is an example, not a
recommendation. Export your own graphs with ComfyUI's *Save (API format)*.

The tests check these files offline (workflow links resolve, harness shards and resumes).
They have **not** been rendered end-to-end on a pod in this form.

```bash
# on the pod, after provision-comfyui.sh flux:
bash /workspace/launch-sharded.sh /workspace/job/batch_harness.py /workspace/job \
    "--jobs /workspace/job/jobs.json --out /workspace/out"
```
