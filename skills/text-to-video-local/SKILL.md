---
name: text-to-video-local
description: Generate video from text or image prompts using local, open-source models — Wan2.2, HunyuanVideo, LTX-Video, CogVideoX, Mochi, and AnimateDiff — with practical guidance on VRAM budgets, model selection, resolution, and frame counts. Use when the user wants to create AI video clips on their own machine, generate a text-to-video shot, turn a prompt into a video, or run a local video generation model.
metadata:
  promptSignals:
    phrases:
      - generate a video from text
      - text to video
      - text-to-video
      - video from a prompt
      - prompt to video
      - local video model
      - ai video generation
      - local video generation
      - wan video
      - hunyuanvideo
      - ltx video
      - cogvideo
      - animatediff
      - generate a clip
---

# Local Text-to-Video Generation

Running open video models locally. Every model here is open-weights and
runnable offline; the hard part is not the model, it is picking the right one
for your VRAM and picking settings that don't produce garbage.

## Model selection by VRAM

| VRAM | Model | Repo | Notes |
|---|---|---|---|
| 24GB+ | Wan2.2 (14B) | `Wan-Video/Wan2.2` | Best quality/size tradeoff. Apache-2.0. |
| 16–24GB | HunyuanVideo | `Tencent-Hunyuan/HunyuanVideo` | Strong prompt adherence. Needs offload. |
| 8–16GB | LTX-Video / LTX-2 | `Lightricks/LTX-Video` | Fastest. Good for iteration. |
| 8–16GB | CogVideoX | `zai-org/CogVideo` | Mature, many distilled variants. |
| 6–8GB | AnimateDiff + SD1.5 | `guoyww/AnimateDiff` | Old but tiny. LoRA ecosystem. |
| 24GB+ | Mochi 1 | `genmoai/mochi` | Strong motion coherence. |

**Start with LTX-Video on ≤16GB.** It generates in seconds, so you can iterate on
the prompt instead of waiting 10 minutes per take.

## Installation

LTX-Video:

```bash
git clone https://github.com/Lightricks/LTX-Video.git
cd LTX-Video
python -m pip install -e '.[inference]'
```

Wan2.2 — checkpoints come from HuggingFace or ModelScope:

```bash
git clone https://github.com/Wan-Video/Wan2.2.git
cd Wan2.2
pip install -r requirements.txt

pip install "huggingface_hub[cli]"
huggingface-cli download Wan-AI/Wan2.2-T2V-A14B --local-dir ./Wan2.2-T2V-A14B
```

## Generating a clip

LTX-Video — text to video. The CLI is driven by a dataclass-backed argument
parser, so the flags are the config field names:

```bash
python inference.py \
  --prompt "A slow push-in on a rusted lighthouse at dusk, waves breaking, volumetric light" \
  --output_path outputs/lighthouse \
  --pipeline_config configs/ltxv-13b-0.9.8-distilled.yaml \
  --height 704 --width 1216 \
  --num_frames 121 --frame_rate 30 \
  --seed 171198
```

`--output_path` is a **directory**, not a file — the pipeline names the output
file itself. `--pipeline_config` selects the model checkpoint and sampling
setup; the `configs/` directory holds the shipped variants (13B dev, 13B
distilled, and smaller ones). Step count and guidance live inside that YAML,
not on the command line.

Image or video to video — condition on a first frame:

```bash
python inference.py \
  --prompt "The camera pushes in, waves begin breaking against the rocks" \
  --conditioning_media_paths first_frame.png \
  --conditioning_start_frames 0 \
  --conditioning_strengths 1.0 \
  --height 704 --width 1216 --num_frames 121 \
  --pipeline_config configs/ltxv-13b-0.9.8-distilled.yaml
```

`--conditioning_media_paths` takes one or more paths, and
`--conditioning_start_frames` takes one frame index per path.

Wan2.2 — text to video. `--task` selects the variant; `t2v-A14B` is the
14B text-to-video model and `ti2v-5B` is the smaller combined one:

```bash
python generate.py \
  --task t2v-A14B \
  --ckpt_dir ./Wan2.2-T2V-A14B \
  --size 1280*720 \
  --prompt "A slow push-in on a rusted lighthouse at dusk, waves breaking" \
  --sample_steps 50 \
  --sample_guide_scale 6.0 \
  --offload_model True \
  --convert_model_dtype
```

Image to video adds `--image`:

```bash
python generate.py \
  --task i2v-A14B \
  --ckpt_dir ./Wan2.2-I2V-A14B \
  --size 1280*720 \
  --image examples/i2v_input.JPG \
  --prompt "A white cat in sunglasses sits on a surfboard, shallow focus"
```

If you OOM, `--offload_model True`, `--convert_model_dtype` and `--t5_cpu`
reduce GPU memory. For multi-GPU, run the same script under `torchrun` with
`--dit_fsdp --t5_fsdp --ulysses_size N`.

Wan2.2 also has an **s2v** task that drives a face from an audio track, and
`--enable_tts` synthesises the audio with CosyVoice in the same run.

## Prompt structure for video

Video prompts need **motion**, not just a scene. A still-image prompt produces a
flickering mess.

```
[SUBJECT] + [ACTION/MOTION] + [ENVIRONMENT] + [CAMERA] + [LIGHTING] + [STYLE]
```

Good:
> A rusted lighthouse rotating slowly, waves crashing against rocks, slow push-in, golden hour backlight, cinematic, 35mm film

Bad:
> A lighthouse, ocean, sunset

Weak prompts:
> A rusted lighthouse, waves crashing, slow push-in, golden hour backlight, cinematic, 35mm film

The difference is the **subject's own motion** ("rotating slowly"). Without it
the model has nothing to animate.

Camera vocabulary that models understand: `static`, `pan left/right`,
`push in`, `pull out`, `tilt up/down`, `dolly`, `tracking shot`, `crane up`,
`handheld`, `orbit`.

## Settings that matter

**Frame count** — models are trained on a fixed window, and asking for more
frames than that does not extend the clip; it degrades it. LTX-Video defaults
to 121 frames at 30fps (about 4 seconds) and Wan2.2 wants `4n+1` frames.
Generate short, then extend or concatenate.

**Resolution** — native training resolutions are safest:
- LTX-Video: 704×1216 (the default), 768×1344
- Wan2.2: 1280×720, 1280×704
- HunyuanVideo: 1280×720

Going above native causes artifacts. Generate small, upscale with
`video-upscale-interpolate`.

**Guidance scale** — 5–7 for most. Above 9 oversaturates and freezes motion;
below 4 loses prompt adherence.

**Negative prompts** — LTX-Video takes `--negative_prompt` directly (it
defaults to `"worst quality, inconsistent motion, blurry, jittery,
distorted"`). Wan2.2 has no negative-prompt flag; steer away from unwanted
content in the prompt instead.
```
blur, watermark, text, deformed, extra limbs, low quality, jpeg artifacts, static image
```

## Memory management

If you OOM, in order of preference:

1. Enable attention slicing / VAE tiling (all diffusers-based models).
2. Use a distilled/few-step checkpoint (LTX-2, Wan 1.3B).
3. Offload the text encoder to CPU while the DiT runs.
4. Reduce frames, then resolution.

For diffusers-based models:

```python
import torch
from diffusers import DiffusionPipeline

pipe = DiffusionPipeline.from_pretrained(
    "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
    torch_dtype=torch.bfloat16,
    variant="fp16",
).to("cuda")
pipe.enable_vae_slicing()
pipe.enable_vae_tiling()
pipe.enable_model_cpu_offload()   # if VRAM is tight
```

## Quality checklist

Before accepting a clip:

- [ ] Motion is coherent across the whole duration, not just the first second
- [ ] No morphing faces or hands in the last third
- [ ] The subject stays roughly where the prompt put it
- [ ] Colour does not drift or flicker
- [ ] Resolution and duration match your edit (see `media-transcode-pipeline`)

## Composing multiple clips

Generated clips are 3–6 seconds each. Build a longer video by generating shots
with a consistent style suffix appended to every prompt:

```
STYLE_SUFFIX = ", cinematic, 35mm film, shallow depth of field, warm golden hour, consistent color grading"
```

Append it to every shot prompt. Then assemble with `shorts-reels-pipeline` or
`media-transcode-pipeline`.

## Reference tools

Other open-source video tools worth knowing, each over 1,000
GitHub stars — see `references/video-reference-tools.md`.

## Related skills

`comfyui-video-workflows` · `video-upscale-interpolate` ·
`shorts-reels-pipeline` · `media-transcode-pipeline` · `local-diffusion-suite`
