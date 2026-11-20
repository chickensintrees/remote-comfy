# Comfy Cloud as a second backend

**Context.** Comfy Cloud (https://cloud.comfy.org) runs API-format workflows on its own
GPUs and bills only while a workflow runs. A forgotten job cannot keep billing, so the
watchdog, the sync loop, provisioning and GPU choice all fall away. What it gives up: only
"the most-used" custom nodes (no published list), your own models only on Creator and
above, a 30-minute run limit (1 hour on Pro), 1 to 5 concurrent jobs by plan, client
images on Comfy's servers, and no stated output retention. Plain pods stay the default for
long saturated batches and anything with an unusual node or model.

Comfy has two APIs. The ComfyUI-shaped **v1** (`/api/prompt`, `X-API-Key`) is "deprecated
in favor of" **v2** (`/api/v2/jobs`, `Authorization: Bearer`), with no date given. On
2026-11-20 RunPod's REST v1 was found retired five days earlier with every pod command
broken, so the job loop is built on v2 from the start.

**Decision (2026-11-20).** `comfy_client.CloudComfy`, with the same calls as `Comfy`
(`wait_ready`, `nodes`, `has`, `upload`, `run`), chosen by `connect("cloud")`:

- `run`: `POST /api/v2/jobs {"workflow": ...}`, poll `GET /api/v2/jobs/{id}` until
  `succeeded` / `failed` / `canceled` / `expired`, then fetch every `outputs[].url`.
  On a timeout it sends `POST /api/v2/jobs/{id}/cancel` so the job stops billing.
- `upload`: `POST /api/v2/assets`, returning the `{"__type": "core/ASSET", "info": {...}}`
  reference the v2 spec says goes where a filename would. `upload(..., api="v1")` uses
  `/api/upload/image` and returns a plain filename instead.
- `nodes`: v1 `GET /api/object_info`. v2 has no node listing; the v2 overview says
  Cloud-specific features stay on v1.
- Key: `COMFY_CLOUD_API_KEY`, else the OS keyring. It is never put in a URL, so the v1
  WebSocket (`?token=<key>`) is not used. Redirects to storage go out with no headers.
- `batch_harness.py --comfy cloud --inputs DIR` uploads any `set` value naming a file in
  DIR and substitutes what `upload` returned.

**Live run (2026-11-20, later the same day).** The docs disagreed with themselves in three
places. A real key and two `cutout_birefnet` jobs settled all three:

1. `LoadImage` takes the v2 `core/ASSET` reference. `batch_harness.py --comfy cloud
   --inputs` uploaded a JPEG, ran the graph in about 5 s, and returned a 560x373 RGBA PNG
   with a real mask (51% transparent).
2. `outputs[].url` is `https://cloud.comfy.org/api/v2/assets/{id}/content`. Without the key
   it answers 401; with Bearer it answers 302 to a signed `storage.googleapis.com` URL,
   which serves the file with no key. The client's own fetch was logged: the key went to
   `cloud.comfy.org` only. `url_expires_at` was 30 days out.
3. `nodes()` lists 3,900 node types and 1,564 model files. Every node and model file in 6
   of the 7 example graphs exists; `image_to_3d.json` lacks the TRELLIS.2 and Pixal3D
   weights, so 3D stays on a pod. Of the catalogue, most video, audio and utility models
   are present; FLUX.3 Klein, Qwen-Image 2.1, TRELLIS.2 and MoGe-3 are not.

Before the key existed, a made-up key got 401 with the documented `{"error": {"code":
"unauthorized", ...}}` body, saying keys start with `comfyui-`.

**Rejected.** The v1 job loop: deprecated, and its only typed output listing is the
WebSocket, which carries the key in the URL. `GET /api/v2/jobs` (listing): Cloud answers
501. The v2 SSE event stream: polling is enough at these job lengths.

**Would change it.** A later run contradicting points 1 to 3; Comfy publishing a v1
shutdown date (drop the v1 calls); a node listing in v2.
