# Open questions

**Do not treat these as settled.** Each is something the toolkit implies but has not
verified. They are written down so nobody re-derives them, or trusts them by accident.
When you settle one, move the result into a test plus `docs/traps.md` (or a
`decisions/` note) and delete it here.

- **`--disable-cuda-malloc` is unproven.** It is in `launch-sharded.sh` and tripwired,
  with the rationale "the async pool hides free VRAM -> partial model load". But the
  fastest sampling ever measured (**4.81 s/it**) was *under* the async allocator, and the
  A/B was still running when the session ended. The tripwire asserts only that our
  launcher is internally consistent — it is **not** evidence the flag helps. Finish the
  A/B before quoting it as fact.
- **Optimal render resolution is unresolved.** 1792x768 beat both 3136x1344 and
  1904x816, and the token-grid theory (dimensions divisible by 16) is a hypothesis fitted
  to two data points.
- **Z-Image never got a clean read** — blocked by the `ae.safetensors` filename collision.
- **Qwen3-TTS remains unavailable** — the node pack's isolated runtime crashes the worker
  (`Worker closed the response stream unexpectedly`); VRAM suspected, untested.
- **`autostop.py` polls only one ComfyUI (`--comfy`, default :8188).** With
  `launch-sharded.sh` there is one instance per GPU on 8188+N, so the watchdog sees only
  GPU0's queue. The launcher compensates by refreshing `/workspace/.busy` while any shard
  runs (tripwired). Polling every port would be the real fix; not done yet.
- **The launcher's queue-clear has only run against a fresh pod.** The python helpers
  ran live on 2026-10-23 (both instances reported READY, the batch completed), but no
  stale queue existed to clear, so the clear-before-relaunch path is still unproven live.
- **`int8_convrot` and the 2026-09 Comfy-Org repo renames are untested here.** The
  catalogue points at renamed repos (old names 307-redirect) and int8_convrot files; the
  built-in `flux`/`wan`/`qwen` provision sets still use the old repo names. `hf download`
  is expected to follow the redirect but has not been watched doing it.
- **What a Comfy Cloud job costs, and how it compares with a pod.** The client ran live on
  2026-11-20 (two 5-second cutouts), but no per-job cost or long-batch throughput has been
  measured, and the 1-to-5 concurrent-job limits have not been hit. See
  `decisions/2026-11-20-comfy-cloud-backend.md`.
