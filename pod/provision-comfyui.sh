#!/usr/bin/env bash
# Provision ComfyUI on a fresh pod, in the ONLY order that works.
# Every step here is a failure we actually hit (2026-07-25) — do not reorder.
#
#   scp provision-comfyui.sh root@<ip>:/workspace/
#   ssh -p <port> root@<ip> 'nohup setsid bash /workspace/provision-comfyui.sh wan \
#       > /workspace/prov.log 2>&1 </dev/null & disown'
#
# Arg 1 = model set: wan | qwen | flux | kontext | 3d | none   (space separated, e.g. "qwen flux")
# Then:  python3 /workspace/autostop.py --pod-id <id> --idle-min 90   (cost guard)
set -u
SETS="${*:-none}"
LOCK=/workspace/.busy
touch "$LOCK"                    # watchdog must NOT stop the pod mid-provision
trap 'rm -f "$LOCK"' EXIT        # ...but always release, even on failure

export HF_HOME=/workspace/.hf HF_HUB_DISABLE_XET=1 HF_HUB_ENABLE_HF_TRANSFER=1
cd /workspace
[ -d ComfyUI ] || git clone --depth 1 https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
pip install -q -r requirements.txt
pip install -q "huggingface_hub[cli,hf_transfer]" sqlalchemy pillow numpy imageio-ffmpeg

# --- system deps for AUDIO custom nodes (image/video nodes never need these) -----
# TTS-Audio-Suite hard-aborts without them; RVC shells out to ffmpeg; and the runpod
# pytorch image ships NO system ffmpeg (imageio-ffmpeg is only a python wrapper).
# (2026-07-26, verified on a live pod)
apt-get update -qq 2>/dev/null && apt-get install -y -qq ffmpeg libsamplerate0-dev portaudio19-dev 2>/dev/null || true

mkdir -p models/{diffusion_models,vae,text_encoders,clip_vision,style_models,checkpoints,loras}

# --- custom nodes FIRST, torch pin LAST -----------------------------------------
# ORDER MATTERS: a custom node's requirements.txt with a bare `torch>=2.0.0` will
# RE-RESOLVE torch and can silently swap the CUDA variant (seen: 2.4.1+cu124 -> +cu121
# while torchaudio stayed cu124 -> torchaudio refuses to import -> ComfyUI dies in
# comfy/sd.py). So install nodes first, then pin the trio, then verify.
cd custom_nodes
for r in kijai/ComfyUI-WanVideoWrapper kijai/ComfyUI-KJNodes Kosinkadink/ComfyUI-VideoHelperSuite; do
  d=$(basename "$r"); [ -d "$d" ] || git clone --depth 1 "https://github.com/$r"
  [ -f "$d/requirements.txt" ] && pip install -q -r "$d/requirements.txt" || true
done
cd /workspace/ComfyUI

# --- torch TRIO, always together, pinned AFTER nodes -----------------------------
# torch 2.4 (the stock runpod image) lacks scaled_dot_product_attention(enable_gqa),
# which Qwen-Image-Edit needs. And bumping torch WITHOUT torchvision+torchaudio leaves
# a stale ABI -> ComfyUI dies at import with "libtorchaudio.so: undefined symbol".
# >= 2.7 since 2026-10: ComfyUI pins comfy-kitchen, whose custom ops use list[int]
# annotations torch 2.6 rejects ("infer_schema ... unsupported type list[int]").
# This trio verified on an RTX 4090 pod (driver CUDA 13.2), 2026-10-20.
echo "== torch trio (pinned after custom nodes) =="
pip install -q torch==2.14.0 torchvision==0.29.1 torchaudio==2.11.0 \
    --index-url https://download.pytorch.org/whl/cu126
python3 - <<'PY'
import sys, torch, torchvision, torchaudio   # all three MUST import or ComfyUI won't boot
def cu(v):                                    # "2.6.0+cu124" -> "cu124"
    return v.split("+")[1] if "+" in v else "none"
print("torch", torch.__version__, "| vision", torchvision.__version__, "| audio", torchaudio.__version__)
# THE INVARIANT IS AGREEMENT, not a specific variant (2026-07-26).
bad = {cu(torch.__version__), cu(torchaudio.__version__), cu(torchvision.__version__)}
assert len(bad) == 1, "CUDA VARIANT MISMATCH %s - a custom node re-resolved torch; re-pin the trio" % bad
assert torch.cuda.is_available(), "CUDA not visible"
print("cuda variants agree:", bad.pop(), "| gpu:", torch.cuda.get_device_name(0))
import comfy_kitchen   # ComfyUI imports it at startup; a too-old torch fails HERE, loudly
print("comfy_kitchen imports")
PY

# --- models ---------------------------------------------------------------------
# NOTE: HF paths shift. Some files are at the repo ROOT, some under split_files/.
# Verify with https://huggingface.co/api/models/<repo> before adding a new line.
# STAGE ON THE VOLUME, NEVER /tmp. The container overlay is only ~40GB, so a 35GB model
# (FLUX.2 fp8mixed) cannot stage there — it fails SILENTLY as a MISS while every smaller
# file in the same run succeeds, which makes it look like a bad HF path (2026-07-26).
STAGE=/workspace/.dl
MISSES=0
# A MISS must be LOUD. Twice on 2026-07-26 a file silently failed to land and the symptom
# appeared much later as something else entirely: (a) FLUX.2's 35GB staged to a too-small
# /tmp -> looked like a bad HF path; (b) Z-Image's VAE had a nonexistent mv target -> the
# run died deep in KSampler as "shape '[1,16,48,2,84,2]'". Always mkdir the DEST too.
dl(){ echo "DL $2"; mkdir -p "$STAGE" "$3"
      if hf download "$1" "$2" --local-dir "$STAGE" >/dev/null 2>&1 && mv -f "$STAGE/$2" "$3/"; then
        echo "  OK $(basename "$2") $(du -h "$3/$(basename "$2")" 2>/dev/null | cut -f1)"
      else
        echo "  *** MISS $1/$2 ***"; MISSES=$((MISSES+1))
      fi; }

for s in $SETS; do case "$s" in
  wan)
    dl Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors models/diffusion_models
    dl Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors models/diffusion_models
    dl Comfy-Org/Wan_2.1_ComfyUI_repackaged split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors models/text_encoders
    dl Comfy-Org/Wan_2.1_ComfyUI_repackaged split_files/vae/wan_2.1_vae.safetensors models/vae ;;
  qwen)
    dl Comfy-Org/Qwen-Image-Edit_ComfyUI split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors models/diffusion_models
    dl Comfy-Org/Qwen-Image_ComfyUI split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors models/text_encoders
    dl Comfy-Org/Qwen-Image_ComfyUI split_files/vae/qwen_image_vae.safetensors models/vae ;;
  flux)   # all-in-one checkpoint (model+CLIP+VAE) -> CheckpointLoaderSimple, outputs 0/1/2
    dl Comfy-Org/flux1-dev flux1-dev-fp8.safetensors models/checkpoints
    dl Comfy-Org/flux1-redux-dev flux1-redux-dev.safetensors models/style_models
    dl Comfy-Org/sigclip_vision_384 sigclip_vision_patch14_384.safetensors models/clip_vision ;;
  flux2)  # FLUX.2 [dev]: bare UNET + Mistral-3 text encoder. 33GB fp8mixed.
          # RUN IT ON cc>=8.9 (Ada/Hopper/Blackwell). On an A40 (cc 8.6, no native fp8)
          # the fp8 weights are emulated: ~225s/frame @20 steps vs seconds on Hopper.
          # Turbo LoRA drops 20 steps -> 8. (measured 2026-07-26)
    dl Comfy-Org/flux2-dev split_files/diffusion_models/flux2_dev_fp8mixed.safetensors models/diffusion_models
    dl Comfy-Org/flux2-dev split_files/text_encoders/mistral_3_small_flux2_fp8.safetensors models/text_encoders
    dl Comfy-Org/flux2-dev split_files/vae/flux2-vae.safetensors models/vae
    dl Comfy-Org/flux2-dev split_files/loras/Flux2TurboComfyv2.safetensors models/loras ;;
  kontext)  # bare UNET -> UNETLoader + DualCLIPLoader + VAELoader
    dl Comfy-Org/flux1-kontext-dev_ComfyUI split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors models/diffusion_models
    dl comfyanonymous/flux_text_encoders clip_l.safetensors models/text_encoders
    dl comfyanonymous/flux_text_encoders t5xxl_fp8_e4m3fn.safetensors models/text_encoders
    dl Comfy-Org/Lumina_Image_2.0_Repackaged split_files/vae/ae.safetensors models/vae ;;
  3d)  # native Pixal3D + TRELLIS.2 (ComfyUI core since PR #14718, 2026-08-22), bf16 for 24GB+ cards.
       # The official template's switch node loads BOTH diffusion models, so ship both.
       # int8_convrot variants (~5.5GB each) exist for <=12GB cards; they need comfy-kitchen kernels.
    dl Comfy-Org/Pixal3D diffusion_models/pixal3d_bf16.safetensors models/diffusion_models
    dl Comfy-Org/TRELLIS.2 diffusion_models/trellis_2_bf16.safetensors models/diffusion_models
    dl Comfy-Org/Pixal3D vae/trellis_2_shape_vae_bf16.safetensors models/vae
    dl Comfy-Org/Pixal3D vae/trellis_2_texture_vae_bf16.safetensors models/vae
    dl Comfy-Org/Pixal3D clip_vision/dino_v3_L_naf_fp32.safetensors models/clip_vision
    dl Comfy-Org/MoGe geometry_estimation/moge_2_vitl_normal_fp16.safetensors models/geometry_estimation
    dl Comfy-Org/BiRefNet background_removal/birefnet.safetensors models/background_removal ;;
  none) : ;;
  *) echo "unknown model set: $s" ;;
esac; done
# Extra models picked from the catalogue: `catalog.py --dl <id>... > extra-models.txt`,
# scp it to /workspace. One "<repo> <path> <dest>" per line. dl's stdin is /dev/null so
# a download can never swallow the remaining lines of the list.
EXTRA=/workspace/extra-models.txt
if [ -f "$EXTRA" ]; then
  while read -r repo path dest; do
    case "$repo" in ''|\#*) continue ;; esac
    dl "$repo" "$path" "$dest" </dev/null
  done < "$EXTRA"
fi
rm -rf "$STAGE"

# --- fail loudly on missing models, BEFORE any workflow runs ---------------------
if [ "$MISSES" -gt 0 ]; then
  echo "!!! $MISSES MODEL FILE(S) MISSING - fix these before running a workflow."
  echo "!!! A missing file does NOT fail cleanly later; it surfaces as a cryptic"
  echo "!!! tensor-shape error or a silently WRONG model. Re-check HF paths:"
  echo "!!!   https://huggingface.co/api/models/<repo>?blobs=true"
fi
echo "== models on disk =="
find models -name "*.safetensors" -size +50M -printf "  %-58f %s\n" 2>/dev/null \
  | awk '{printf "  %-58s %6.1f GB\n", $1, $2/1073741824}'
# NAME COLLISIONS ARE REAL: Z-Image and FLUX both ship a file literally called
# "ae.safetensors". Same name = ComfyUI silently loads whichever it finds -> wrong VAE
# -> failure deep in the sampler. Rename per-family on download (e.g. z_image_ae.safetensors).
dupes=$(find models -name "*.safetensors" -printf "%f\n" 2>/dev/null | sort | uniq -d)
[ -n "$dupes" ] && echo "!!! DUPLICATE MODEL FILENAMES (rename per family): $dupes"

# --- launch ---------------------------------------------------------------------
# nohup setsid + disown: a plain background job dies with SIGHUP when SSH closes.
cd /workspace/ComfyUI
nohup setsid python main.py --listen 0.0.0.0 --port 8188 > /workspace/comfy.log 2>&1 </dev/null & disown
# Poll with PYTHON: the pod image has no curl, so a curl loop could never succeed - and a
# loop that falls through still printed PROVISION_DONE over a dead ComfyUI (2026-10-20).
# /workspace is network storage; first boot can take minutes (15 min ceiling here).
READY=0
python3 - <<'PY' && READY=1
import sys, time, urllib.request
for _ in range(90):
    try:
        if urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=8).status == 200:
            sys.exit(0)
    except Exception:
        pass
    time.sleep(10)
sys.exit(1)
PY
if [ "$READY" = 1 ]; then
  echo "COMFY_READY"
else
  echo "PROVISION_FAILED: ComfyUI never answered on :8188. Last log lines:"
  tail -25 /workspace/comfy.log
  exit 1
fi
echo "PROVISION_DONE"
