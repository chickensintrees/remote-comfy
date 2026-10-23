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
- **The 2026-10-23 launcher fixes are unexercised on a live pod.** The python
  queue-clear/readiness helpers were verified against a fake ComfyUI only.
