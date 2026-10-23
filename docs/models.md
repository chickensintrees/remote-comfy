# Model catalogue

Generated from `catalog/catalog.json` by `python remote_comfy/catalog.py --write-docs`.
Do not edit by hand: a test fails if this file and the JSON disagree.

Checked against Hugging Face on **2026-10-23**. Model lists rot fast: run
`python remote_comfy/catalog.py --verify` and STEP ZERO (`check_latest_models.py`) before committing a batch.

## Text to image

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [FLUX 3 Image Klein (base + distilled)](https://huggingface.co/black-forest-labs/flux-3-image-klein) `flux3-klein` | FLUX Kommunity License v1.0 (flux-kommunity-license) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_flux3_klein_distilled_t2i.json) | 16 GB | 35 GB | Top open-weights T2I on Artificial Analysis (Elo 1043, 2026-10) and #3 for editing; same weights do multi-ref edit. Not if revenue >= $5M or you need clean commercial terms. |
| [Qwen-Image 2.1 (+Turbo)](https://huggingface.co/Qwen/Qwen-Image-2.1) `qwen-image-2.1` | Qwen Research License (qwen-research) (non-commercial) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_turbo_t2i.json) | 20 GB | 34 GB | Best text rendering / 2K native / RGBA output; #2 open T2I and #2 open edit on AA. Not for any commercial job: licence is research-only (unlike Apache-2.0 Qwen-Image-2512). |
| [Krea 2 (Turbo / Raw)](https://huggingface.co/krea/Krea-2-Turbo) `krea-2-turbo` | Krea 2 Community License (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_krea2_turbo_t2i.json) | 20 GB | 32 GB | Aesthetic/photographic look with style LoRAs and a 1-2 image style-reference workflow. Not if revenue > $1M. |
| [Z-Image Turbo (6B)](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) `z-image-turbo` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_z_image_turbo.json) | 16 GB | 27 GB | Cheapest high-volume photoreal batches with a clean Apache licence; huge LoRA ecosystem. Not when you need top prompt adherence/text (AA Elo 936 vs ~1040 for leaders). |
| [MOSS-Image (SFT / Base)](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT) `moss-image` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_moss_image_t2i.json) | 16 GB | 23 GB | Newest Apache-2.0 T2I with bounding-box layout control (image_moss_image_t2i_bboxes). Not yet ranked on public arenas - test before committing. |

## Image editing / multi-reference

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [Bria Fibo 2.0 (Dev + Edit Turbo, 8B)](https://huggingface.co/briaai/Fibo-2.0-dev) `fibo-2.0-edit` | bria-fibo (upstream) / tagged cc-by-nc-4.0 on Comfy-Org repo (non-commercial) | native | 16 GB | 24 GB | #1 open-weights image editing on AA (Elo 1088) and #3 T2I; JSON structured prompts; trained on licensed data. Not for commercial use without a Bria agreement. |
| [Qwen-Image 2.1 (edit mode, up to 16 refs)](https://huggingface.co/Qwen/Qwen-Image-2.1) `qwen-image-2.1-edit` | Qwen Research License (qwen-research) (non-commercial) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_turbo_image_edit.json) | 20 GB | 31 GB | Multi-reference compositing (10 wired, 16 max), RGBA edits, background removal template. Research-only licence. |
| [Qwen-Image-Edit 2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) `qwen-image-edit-2511` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_edit_2511_int8.json) | 24 GB | 52 GB | Best commercially clean (Apache) editor with a big LoRA ecosystem (multi-angle, relight, fusion). Lower quality than Fibo 2.0/Qwen 2.1 (AA Elo 991). |
| [FLUX.2 [klein] 4B (distilled + base)](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) `flux2-klein-4b` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_flux2_klein_image_edit_4b_distilled.json) | 12 GB | 16 GB | Fast, small, Apache-licensed multi-reference edit + T2I in one model. Quality well below FLUX 3 Klein (AA edit Elo 938). |

## Text to video

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [MiniMax H3 (T2V / I2V / R2V with native stereo audio)](https://huggingface.co/MiniMaxAI/MiniMax-H3) `minimax-h3` | MiniMax H3 Community License Agreement (other) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json) | 48 GB | 63 GB | Clearly the strongest open-weights video model (AA T2V Elo 1158, I2V 1140 - only model near closed frontier); audio+video, multi-reference R2V, continuation, ControlNet-union. Do NOT use if the operator, the RunPod region or the output audience is in the US/EU/UK/KR. |
| [LTX-2.5 (22B, audio+video, up to 4K/50fps)](https://huggingface.co/Lightricks/LTX-2.5) `ltx-2.5` | LTX-2.x Community License Agreement (other) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_ltx2_5_t2v.json) | 32 GB | 75 GB | Second-best open video (AA T2V 949) with synced audio, the best ecosystem of IC-LoRAs (upscale, HDR, alpha, refine) and territory-unrestricted terms under $10M. Weaker motion/quality than MiniMax H3. |
| [Wan 2.2 T2V A14B (MoE high/low noise)](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B) `wan2.2-t2v-a14b` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_t2v.json) | 24 GB | 38 GB | The only top-tier video family with a plain Apache licence and the deepest LoRA/control ecosystem (VACE, Fun, Animate, S2V). Silent, 480-720p, older (2025-07) and not on AA open boards. |
| [HunyuanVideo 1.5 (8.3B)](https://huggingface.co/tencent/HunyuanVideo-1.5) `hunyuanvideo-1.5` | tencent-hunyuan-community (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_hunyuan_video_1.5_720p_t2v.json) | 16 GB | 38 GB | Small and fast for 24GB cards with built-in 1080p super-resolution stage. Silent, below LTX-2.5/H3 quality. |

## Image to video

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [MiniMax H3 I2V / FLF2V / continuation](https://huggingface.co/MiniMaxAI/MiniMax-H3) `minimax-h3-i2v` | MiniMax H3 Community License Agreement (other) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_i2v.json) | 48 GB | 46 GB | Best open I2V (AA 1140). Shares text encoder/VAEs with minimax-h3 entry. Same territory caveat. |
| [LTX-2.5 I2V / FLF2V / DFR](https://huggingface.co/Lightricks/LTX-2.5) `ltx-2.5-i2v` | LTX-2.x Community License Agreement (other) (conditional) | [native](https://github.com/Lightricks/ComfyUI-LTXVideo) · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_ltx2_5_i2v.json) | 32 GB | 22 GB | Territory-unrestricted I2V with audio; first/last-frame and DFR (diffusion fidelity) modes. Plus text encoders/VAEs listed under ltx-2.5. |
| [Wan 2.2 I2V A14B](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B) `wan2.2-i2v-a14b` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_i2v.json) | 24 GB | 38 GB | Apache-licensed I2V workhorse with mature 4-step LoRAs and FLF2V; best when licence cleanliness or LoRA availability matters more than peak quality. |

## Video to video / restyle / extend

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [Wan Animate 2 (character animate / replace)](https://huggingface.co/Wan-AI/Wan2.2-Animate-2-14B-Diffusers) `wan-animate-2` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan_animate2_distilled.json) | 24 GB | 42 GB | Drive a still character with a reference performance video, or swap a character into footage; Apache licence. |
| [SCAIL-2 (Wan2.1-14B character replacement)](https://huggingface.co/zai-org/SCAIL-2) `scail-2` | mit | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan21_scail2_character_replacement_int8.json) | 24 GB | 37 GB | MIT-licensed full-body character replacement with SAM 3.1 masking and a relight LoRA. Also needs Wan 2.1 clip_vision_h/umt5/VAE (Comfy-Org/Wan-2.1). |
| [LTX-2.3 22B + IC-LoRAs (in/outpaint, clean-plate, ingredients, restore, style transition)](https://huggingface.co/Lightricks/LTX-2.3) `ltx-2.3-ic-loras` | LTX-2 Community License Agreement (other) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_ltx2_3_ic_lora.json) | 32 GB | 44 GB | Largest catalogue of ready-made video-to-video templates: object/watermark/subtitle removal, outpainting, archival restore, depth/pose/canny control. LTX-2.5 IC-LoRAs are newer but fewer templates. |
| [Wan 2.2 VACE-Fun A14B (v2v, ref2v, inpaint, outpaint, extension)](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B) `wan2.2-vace-fun` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan_vace_14B_v2v.json) | 24 GB | 35 GB | Apache-licensed all-in-one control/edit/extend for video; works with every Wan LoRA. Needs umt5/VAE from Comfy-Org/Wan-2.2. |
| [Netflix VOID (video object removal)](https://huggingface.co/netflix/void-model) `void-video-inpaint` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_void_video_inpainting.json) | 32 GB | 32 GB | Remove an object (incl. its shadows/interactions) from footage with a SAM 3.1 mask; Apache. |

## Lip-sync / talking head / avatar

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [InfiniteTalk (Wan 2.1 14B audio-driven, unlimited length)](https://huggingface.co/MeiGen-AI/InfiniteTalk) `infinitetalk` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_1_infinitetalk.json) | 24 GB | 36 GB | Long-form talking head / dubbing from image or video + audio, single or multi-speaker, Apache. 480p base; upscale after. |
| [LTX-2.3 ID-LoRA TalkVid (image + speech -> talking video)](https://huggingface.co/Lightricks/LTX-2.3) `ltx-2.3-talkvid` | LTX-2 Community License Agreement (other) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/template_image_speech_to_video.json) | 32 GB | 40 GB | Talking head with natural body/camera motion from one image + speech; DubIt IC-LoRA re-syncs lips on existing video. Licence capped at $10M. |
| [Wan 2.2 S2V 14B (speech-to-video)](https://huggingface.co/Wan-AI/Wan2.2-S2V-14B) `wan2.2-s2v` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_wan2_2_14B_s2v.json) | 24 GB | 17 GB | Audio-driven full-scene/body animation with Apache licence; alternative to InfiniteTalk for cinematic shots. |
| [HuMo 17B (text+image+audio human video)](https://huggingface.co/bytedance-research/HuMo) `humo-17b` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_humo.json) | 24 GB | 20 GB | Subject-consistent talking/singing humans from reference image + audio + prompt. Older; InfiniteTalk usually preferred for long clips. |
| [LatentSync 1.6 (lip-sync onto existing video)](https://huggingface.co/ByteDance/LatentSync-1.6) `latentsync-1.6` | openrail++ (conditional) | [custom-node](https://github.com/ShmuelRonen/ComfyUI-LatentSyncWrapper) | 12 GB | 5 GB | Cheap mouth-only re-sync of existing footage (dubbing) when you do not want to regenerate the shot. |

## Upscaling (image and video)

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [SeedVR2 3B/7B (one-step image + video restoration/upscale)](https://huggingface.co/ByteDance-Seed/SeedVR2-7B) `seedvr2` | apache-2.0 | [native](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler) · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_seedvr2_3b_int8_upscale_video.json) | 16 GB | 21 GB | Default generative upscaler for both stills and video, Apache; 3B for video throughput, 7B/7B-sharp for stills. |
| [NVIDIA PiD (PixelDiT latent-to-4K upscaler, 4-step)](https://huggingface.co/Comfy-Org/PixelDiT) `pid-latent-upscale` | nsclv1 (NVIDIA Source Code License - non-commercial) (non-commercial) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_pid_latent_upscale_dit.json) | 16 GB | 6 GB | Upscale a FLUX.2/FLUX3-VAE, Qwen-Image, SD3 or SDXL latent straight to 4096px in 4 steps. Non-commercial. |
| [Real-ESRGAN x4plus (GAN)](https://huggingface.co/Comfy-Org/Real-ESRGAN) `real-esrgan-x4plus` | bsd-3-clause | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility-gan_upscaler.json) | 4 GB | 0 GB | Near-free deterministic upscale for previews or before a generative pass. Not for restoring detail. |
| [RIFE v4.25 heavy / FILM frame interpolation](https://huggingface.co/Comfy-Org/Frame-Interpolation) `rife-film-interp` | mit-and-apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_video_frame_interpolation.json) | 4 GB | 0 GB | Temporal upscaling (16/24fps -> 48/60fps) after video generation; native nodes, no custom pack needed. |

## 3D generation

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [Pixal3D (image / multiview -> PBR mesh)](https://huggingface.co/TencentARC/Pixal3D) `pixal3d` | mit | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/3d_pixal3d_trellis2_image_to_model.json) | 16 GB | 16 GB | Highest-fidelity open image-to-3D with PBR textures in native ComfyUI (built on TRELLIS.2 VAEs); multiview input supported. MIT. |
| [TRELLIS.2 4B](https://huggingface.co/microsoft/TRELLIS.2-4B) `trellis2` | mit | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/3d_pixal3d_trellis2_image_to_model.json) | 16 GB | 9 GB | Proven MIT image-to-3D baseline; same template as Pixal3D lets you A/B them. |
| [TripoSplat (image -> 3D Gaussian splat)](https://huggingface.co/VAST-AI/TripoSplat) `triposplat` | mit | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/3d_triposplat_image_to_gaussian_splat.json) | 8 GB | 3 GB | Fast, small Gaussian-splat output (for viewers/relighting previs) instead of meshes. |
| [Hunyuan3D 2.1](https://huggingface.co/tencent/Hunyuan3D-2.1) `hunyuan3d-2.1` | tencent-hunyuan-community (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/3d_hunyuan3d-v2.1.json) | 12 GB | 7 GB | Mature shape generator with big community; superseded on quality by Pixal3D/TRELLIS.2 in native ComfyUI. |

## Speech / voice cloning

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [Qwen3-TTS 12Hz 1.7B (Base / CustomVoice / VoiceDesign)](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) `qwen3-tts` | apache-2.0 | [custom-node](https://github.com/flybirdxx/ComfyUI-Qwen-TTS) | 8 GB | 5 GB | Best all-round Apache TTS: 3s voice cloning, natural-language voice design, multilingual. Most-starred ComfyUI TTS node (1955 stars, pushed 2026-10-23). |
| [VoxCPM2](https://huggingface.co/openbmb/VoxCPM2) `voxcpm2` | apache-2.0 | [custom-node](https://github.com/wildminder/ComfyUI-VoxCPM) | 8 GB | 5 GB | Tokenizer-free, very natural prosody voice cloning, Apache; ~925k monthly HF downloads. |
| [Resemble Chatterbox (multilingual v3 / Turbo)](https://huggingface.co/ResembleAI/chatterbox) `chatterbox` | mit | [custom-node](https://github.com/filliptm/ComfyUI_Fill-ChatterBox) · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio-chatterbox_tts.json) | 6 GB | 3 GB | MIT voice cloning with emotion control and 23 languages; official Comfy template exists (TTS, dialog, multilingual, voice conversion). |
| [Ming 3.0 TTS (tiny)](https://huggingface.co/inclusionAI/Ming-3.0-tts-tiny) `ming-3.0-tts` | mit | none | - | 9 GB | Watch item: Comfy-Org repackaged it on 2026-10-23, signalling imminent native TTS in ComfyUI core. |

## Music

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [MiniMax Music 3 (full songs up to ~5 min)](https://huggingface.co/MiniMaxAI/MiniMax-Music3) `minimax-music-3` | MiniMax-Music3 Community License (other) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_minimax_music_3.json) | 16 GB | 14 GB | Strongest open full-song generator (vocals + lyrics, long form). Check attribution clause. |
| [ACE-Step 1.5 XL (4B base / SFT / turbo)](https://huggingface.co/ACE-Step/Ace-Step1.5) `ace-step-1.5-xl` | mit | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step1_5_xl_turbo.json) | 16 GB | 29 GB | MIT-licensed, fast song generation with editing/repaint; the safe commercial default. |
| [Stable Audio 3 (medium / small-music / small-sfx)](https://huggingface.co/stabilityai/stable-audio-3-medium) `stable-audio-3` | Stability AI Community License (stable-audio-community) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_stable_audio_3_medium.json) | 12 GB | 15 GB | Instrumentals, stems, loops and SFX from one model family; trained on licensed data. Large model is API-only. |
| [YuE2 3B (lyrics-to-song, covers)](https://huggingface.co/m-a-p/YuE2-3B) `yue2` | cc-by-nc-4.0 (non-commercial) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_yue2_text2music.json) | 8 GB | 5 GB | Cover versions that keep melody from reference audio; symbolic (ABC) planning. Non-commercial. |

## Sound effects / video-to-audio

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [LTX-2.3 Foley V2A LoRA](https://huggingface.co/Lightricks/LTX-2.3-22b-LoRA-Foley-V2A) `ltx-2.3-foley` | LTX-2 Community License Agreement (other) (conditional) | [custom-node](https://github.com/Lightricks/ComfyUI-LTXVideo) | 32 GB | 0 GB | Foley for silent clips (e.g. Wan output) using the LTX-2.3 base you may already have loaded. Trained at ~3.7s windows - long clips need windowing. |
| [HunyuanVideo-Foley (XL)](https://huggingface.co/tencent/HunyuanVideo-Foley) `hunyuanvideo-foley` | tencent-hunyuan-community (conditional) | [custom-node](https://github.com/aistudynow/Comfyui-HunyuanFoley) | 12 GB | 19 GB | Standalone video+text -> 48kHz foley with good sync; works on any model's silent output. |
| [MMAudio large 44k v2](https://huggingface.co/hkchengrex/MMAudio) `mmaudio` | cc-by-nc-4.0 (upstream weights; Kijai repackage tagged mit) (non-commercial) | [custom-node](https://github.com/kijai/ComfyUI-MMAudio) | 6 GB | 5 GB | Fast, light, well-synced V2A for prototyping. Non-commercial weights; old (2024-12). |
| [Stable Audio 3 small-sfx (text-to-SFX)](https://huggingface.co/stabilityai/stable-audio-3-small-sfx) `stable-audio-3-small-sfx` | Stability AI Community License (stable-audio-community) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_stable_audio_3_medium.json) | 6 GB | 3 GB | Text-prompted SFX library generation (not synced to video). |
| [Xiaomi ControlFoley (V2A, text/audio-conditioned)](https://huggingface.co/YJX-Xiaomi/ControlFoley) `controlfoley` | cc-by-nc-4.0 (non-commercial) | [custom-node](https://github.com/YJX-Research/comfyui-controlfoley-official) | - | 11 GB | Newest research V2A with timbre/audio-reference control (ACM MM 2026). Non-commercial; tiny user base (8 stars). |

## Control and utilities

| model | licence | ComfyUI | VRAM | files | pick when |
|---|---|---|---|---|---|
| [SAM 3.1 (text-prompted image/video segmentation)](https://huggingface.co/facebook/sam3.1) `sam3.1` | SAM License (sam-license) (conditional) | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_video_segment_sam3.json) | 4 GB | 2 GB | Masks for inpaint/character replacement/VOID from a text prompt, tracked through video. Upstream is manually gated - use the Comfy-Org mirror. |
| [Depth Anything 3 (mono/metric large)](https://huggingface.co/depth-anything/DA3MONO-LARGE) `depth-anything-3` | apache-2.0 | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_depth_anything3_video_depth_estimation.json) | 4 GB | 3 GB | Default depth for ControlNet/IC-LoRA conditioning, image and video. |
| [BiRefNet (+ lucida) background removal](https://huggingface.co/ZhengPeng7/BiRefNet) `birefnet` | mit | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_birefnet_remove_background.json) | 4 GB | 1 GB | Native cut-outs for product shots and 3D input prep; Qwen-Image 2.1 RGBA is the generative alternative. |
| [SDPose wholebody + RT-DETR v4 detector](https://huggingface.co/teemosliang/SDPose-Wholebody) `sdpose` | mit | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_sdpose_multi_person_video.json) | 4 GB | 2 GB | Multi-person pose maps (image/video) for pose ControlNets and Animate pipelines, natively - replaces DWPose from controlnet_aux. |
| [MoGe 3 (monocular geometry: depth, normals, point maps)](https://huggingface.co/Ruicheng/moge-3-vitl) `moge-3` | mit | native · [workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/utility_moge3_geometry_estimation.json) | 4 GB | 3 GB | Normals/metric geometry and image/panorama-to-mesh; used inside the Pixal3D template. |

## Workflow sources and techniques

- [Comfy-Org/workflow_templates](https://github.com/Comfy-Org/workflow_templates): Source of the in-app template browser; ~719 JSONs incl. api_* (closed-model) ones. templates/index.json carries date, total download size and model URLs per template - machine-readable for a harness.
- [ComfyUI docs tutorials (index)](https://docs.comfy.org/_llms/en/tutorials.txt): LLM-friendly index of all ~256 tutorial pages; every model in this catalogue with native support has a page here.
- [ComfyUI releases](https://github.com/Comfy-Org/ComfyUI/releases): Core repo moved from comfyanonymous/ComfyUI to Comfy-Org/ComfyUI; v0.42.1 (2026-10-19) current; FLUX 3 Klein needs >=0.41.0. Release cadence ~weekly - pin versions in pod images.
- [ComfyUI docs changelog](https://docs.comfy.org/changelog): Per-release notes on new native model support.
- [ComfyUI_examples (legacy)](https://github.com/comfyanonymous/ComfyUI_examples): Last pushed 2025-11-26 - effectively superseded by workflow_templates; do not use for 2026 models.
- [Trend: Comfy-Org-native everything + int8_convrot](https://huggingface.co/Comfy-Org): Since mid-2026 nearly every new open model ships native core nodes (nodes_minimax_h3, trellis2, seedvr, sam3, yue2, ...) plus Comfy-Org repacks in int8_convrot / fp8_scaled / mxfp8 / nvfp4. int8_convrot is now the default precision in templates (Ampere-friendly). Kijai wrapper packs matter less.
- [Trend: Comfy-Org HF repo renames (2026-09-23)](https://huggingface.co/api/models/Comfy-Org/Wan_2.1_ComfyUI_repackaged): Old names (Wan_2.1_ComfyUI_repackaged, Qwen-Image-Edit_ComfyUI, flux2-dev, HuMo_ComfyUI, hunyuan3D_2.1_repackaged) now 307-redirect to new names (Wan-2.1, Qwen-Image-Edit, Flux-2-Dev, HuMo, Hunyuan-3D-2.1). Templates still reference old names - downloader must follow redirects.
- [Trend: joint audio+video models](https://docs.comfy.org/tutorials/video/minimax/minimax-h3): MiniMax H3 and LTX-2.5 generate synced audio natively; foley/V2A becomes a fallback step for Wan-family output.
- [Trend: in-graph LLM prompt expansion](https://docs.comfy.org/tutorials/llm/qwen/qwen3_5): Templates now chain TextGenerate (Qwen3.5 / Gemma 4) prompt upsamplers before the diffusion model (FLUX3 Klein, Qwen-Image 2.1, Stable Audio 3, LTX-2.5) - budget 5-10GB extra VRAM or disable.
- [Lightricks/ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo): Official LTX nodes (4210 stars, pushed 2026-10-20) - needed for DFR, foley and many IC-LoRA workflows.
- [kijai/ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper): Historic Wan bleeding-edge wrapper (6743 stars) but last pushed 2026-05-24 - most Wan variants are now native; use only for features not in core.
- [kijai/ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes): Utility pack still used by official templates (e.g. SUPIR upscale); pushed 2026-10-23. Includes Sage-attention patch / torch.compile helper nodes.
- [nunchux-ai/ComfyUI-nunchaku (SVDQuant 4-bit)](https://github.com/nunchux-ai/ComfyUI-nunchaku): 4-bit SVDQuant inference (2931 stars, pushed 2026-09-06); model coverage lags the newest models - check before relying on it. Org name changed from earlier nunchaku-tech.
- [SageAttention](https://github.com/thu-ml/SageAttention): Quantized attention kernels (3973 stars); launch ComfyUI with --use-sage-attention; biggest win on long video sequences. Last push 2026-01-17.
- [ComfyUI-MagCache](https://github.com/Zehong-Ma/ComfyUI-MagCache): Step-skipping cache (successor to TeaCache); last push 2025-11 - may not cover 2026 architectures. Core now ships EasyCache (comfy_extras/nodes_easycache) natively.
- [ComfyUI-TeaCache](https://github.com/welltop-cn/ComfyUI-TeaCache): Older timestep-embedding cache; unmaintained since 2025-07 - prefer EasyCache/MagCache or distill LoRAs.
- [Distill LoRAs (lightx2v)](https://huggingface.co/lightx2v/Minimax-h3-Turbo): 4/8-step distillation LoRAs are the dominant batch-cost lever in 2026 (MiniMax H3, Wan 2.2, Qwen-Image-Edit, HunyuanVideo 1.5); bigger saving than caching.
- [FastVideo FastH3](https://huggingface.co/FastVideo/FastVideo-FastH3-Comfy): 8-step distilled MiniMax H3 DiTs (T2V/I2V and OmniRef R2V) packaged for ComfyUI with official templates video_fastvideo_fasth3_t2v / video_fasth3_ominiref_r2v.
- [torch.compile (core node)](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_torch_compile.py): Native TorchCompileModel node; worthwhile on long batch runs where compile time amortises.
- [Fannovel16/comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux): Classic preprocessors (lineart, softedge, etc.) still maintained (pushed 2026-10-11); depth/pose/seg now better done with native DA3/SDPose/SAM3.
- [diodiogod/TTS-Audio-Suite](https://github.com/diodiogod/TTS-Audio-Suite): Multi-engine TTS pack (Chatterbox, Qwen, etc.); fills the gap left by no core TTS.
