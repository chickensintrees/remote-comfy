# GPU choice: throughput per dollar

Prices and stock are from mid-2026 and **will drift**. Re-check with
`python remote_comfy/pod_ctl.py availability --min-vram <GB>` before every rental.

Total cost = GPU-hours x rate, so **multi-GPU does not cost more, it just finishes
sooner**. Run one ComfyUI instance per GPU and shard the work.

| config | $/hr | stock @count | rel. throughput | verdict |
|---|---|---|---|---|
| **8x A40 48GB** | $3.52 | **High** | 8.0 | **best throughput/$; only 48GB card with High stock at 8x** |
| 4x L40S 48GB | $3.96 | Medium | 7.2 | newer Ada, fine |
| 4x RTX PRO 6000 96GB | $7.96 | Medium | 10 | fastest + 720p headroom; needs **cuda12.8/torch2.7** image |
| 2x H100 80GB | $5.98 | High | 7.0 | worst throughput/$ |

48GB is the floor for Wan 2.2 I2V A14B @480p (weights + T5 + VAE, GPU-resident); 24GB
forces offload. Match arch to the image: Ada/Ampere for cuda12.4, Blackwell needs 12.8+.

**Managed ComfyUI services** (saturated 554-clip batch, ~4.6 GPU-hrs): RunPod 8xA40
~$2-4 · fal/Replicate ~$17 · RunComfy A100 ~$23 · Comfy.ICU L40S ~$53. Comfy.ICU
pre-installs WanVideoWrapper but forbids custom-node installs and bills per-second
(good for bursty one-offs, bad for a full batch). Both need account signup.
