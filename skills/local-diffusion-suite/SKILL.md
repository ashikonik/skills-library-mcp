---
name: local-diffusion-suite
description: Choose and run local open-source image generation tools — AUTOMATIC1111 WebUI, Forge, InvokeAI, Fooocus, Diffusers, and Flux — with model selection, SDXL vs SD1.5 vs Flux comparison, VRAM requirements, and the API for scripted generation. Use when the user wants to generate images locally, pick a diffusion model, or set up a local image generation stack.
metadata:
  promptSignals:
    phrases:
      - local image generation
      - stable diffusion local
      - run diffusion model
      - automatic1111
      - forge webui
      - invokeai
      - fooocus
      - flux model
      - sdxl checkpoint
      - diffusers library
---

# Local Diffusion Suite

Picking and running an open image model locally. The models are the same across
tools; what differs is the UI, the memory efficiency, and the automation story.

## Choosing a tool

| Tool | Repo | Best for | VRAM |
|---|---|---|---|
| **A1111 WebUI** | `AUTOMATIC1111/stable-diffusion-webui` | Maximum control, huge extension ecosystem | 6–8GB |
| **Forge** | `lllyasviel/stable-diffusion-webui-forge` | A1111 UI with much better memory use | 4–6GB |
| **InvokeAI** | `invoke-ai/InvokeAI` | Professional workflow, canvas, inpainting | 8GB+ |
| **Fooocus** | `lllyasviel/Fooocus` | Fastest good-looking results, minimal setup | 6GB+ |
| **Diffusers** | `huggingface/diffusers` | Scripting, pipelines, research | flexible |
| **ComfyUI** | `Comfy-Org/ComfyUI` | Node graphs, reproducibility | 6GB+ |

**Start with Fooocus** if you want images without configuration. **Start with
Forge** if you want A1111's feature set on limited VRAM. **Start with Diffusers**
if you need programmatic control.

## Model families

| Model | Base | Size | VRAM (fp16) | Quality notes |
|---|---|---|---|---|
| SD 1.5 | SD1.5 | 2GB | 4GB | Fast, huge LoRA ecosystem, dated aesthetics |
| SDXL 1.0 | SDXL | 6.5GB | 8GB | The workhorse. Great base for fine-tunes |
| SDXL Turbo | SDXL | 6.5GB | 8GB | 1–4 steps, no CFG. Fast |
| SD 3 / 3.5 | SD3 | 8GB | 10GB | Better text rendering, newer arch |
| FLUX.1 dev | FLUX | 12GB | 16GB | Best prompt adherence, needs bf16 |
| FLUX.1 schnell | FLUX | 12GB | 16GB | 4 steps, Apache-2.0 licensed |
| FLUX.1-schnell GGUF | quantized | 2–8GB | 4–12GB | Runs on consumer cards |
| Playground v2.5 | SDXL | 7GB | 10GB | Strong aesthetics |

FLUX is the current quality leader but needs 16GB+ unless quantized. SDXL is
the pragmatic default.

## Install

### Forge (recommended for A1111 users)

```bash
git clone https://github.com/lllyasviel/stable-diffusion-webui-forge.git
cd stable-diffusion-webui-forge
python launch.py --listen
```

Forge uses the A1111 extension ecosystem with far better memory management —
it patches attention and offloads aggressively.

### Fooocus

```bash
git clone https://github.com/lllyasviel/Fooocus.git
cd Fooocus
pip install -r requirements_versions.txt
python entry_with_update.py
```

No configuration. Downloads models on first run. Minimum 4GB VRAM.

`--preset anime` and `--preset realistic` select the model presets;
`--listen` exposes the UI on the network.

### InvokeAI

The recommended path is the Invoke Launcher (Windows/macOS/Linux), which
installs and updates Invoke for you. For a manual install, use `uv`:

```bash
uv venv --relocatable --prompt invoke --python 3.12 \
  --python-preference only-managed .venv
source .venv/bin/activate
uv pip install invokeai
invokeai-web --root ~/invokeai
```

`invokeai-web` is the console entry point (`invokeai.app.run_app`). Other
entry points: `invoke-useradd`, `invoke-userlist`, `invoke-usermod`,
`invoke-db-copy`.

### Diffusers (scripting)

```bash
pip install torch diffusers transformers accelerate safetensors
```

```python
import torch
from diffusers import StableDiffusionXLPipeline

pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16,
    variant="fp16",
).to("cuda")

pipe.enable_attention_slicing()
pipe.safety_checker = None

prompt = "a weathered fishing boat on a misty lake at dawn, cinematic, 35mm"
image = pipe(prompt, num_inference_steps=30, guidance_scale=7.0).images[0]
image.save("out.png")
```

### FLUX

```bash
pip install torch diffusers transformers accelerate sentencepiece protobuf
```

```python
import torch
from diffusers import FluxPipeline

pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
pipe.to("cuda")
image = pipe("a lighthouse in a storm", num_inference_steps=4,
             guidance_scale=0.0).images[0]
```

FLUX **must** run in bf16 on Ampere+ (RTX 30/40 series). fp16 produces black
images. On older cards, use the GGUF quantized build via
`ComfyUI-GGUF` or `diffusers` with `BitsAndBytesConfig`.

## Checkpoint and LoRA placement

```
ComfyUI/models/checkpoints/   SDXL, SD1.5, Flux .safetensors
ComfyUI/models/loras/         LoRA .safetensors
A1111/models/Stable-diffusion/  checkpoints and LoRAs
```

For LoRA, weight around 0.7–1.0. Above 1.2 the output starts to break.

## Prompting

**Positive**: subject, style, quality terms, composition.

```
"an elderly fisherman mending nets, weathered hands, golden hour rim light,
portrait, 85mm, shallow depth of field, highly detailed, film grain"
```

**Negative** (SD1.5/SDXL):

```
"lowres, bad anatomy, bad hands, text, watermark, signature, jpeg artifacts,
blurry, deformed, extra fingers, cropped"
```

**FLUX** handles prompts far more literally and does not need a negative prompt
or quality tags like "highly detailed" — it treats them as literal content.
Write natural sentences for FLUX.

SDXL adds a **refiner** pass (optional) and responds to microtag weighting with
`(term:1.2)` syntax. FLUX does not support weight syntax.

## Sampler settings

| Model | Steps | CFG |
|---|---|---|
| SD1.5 | 25–30 | 7–9 |
| SDXL | 25–35 | 5–8 |
| SDXL Turbo | 1–4 | 1–2 |
| FLUX dev | 28–50 | 3.5 |
| FLUX schnell | 4 | 0.0 |

Higher CFG past ~12 on SD1.5 burns colours and over-saturates.

## VRAM management

In order of preference:

1. **Forge instead of A1111** — same UI, 2GB less VRAM.
2. **Quantize the weights** — GGUF for Flux (4-bit Q4 works on 8GB).
3. **Enable attention slicing** in Diffusers.
4. **Use `--medvram` / `--lowvram`** launch flags in A1111/Forge.
5. **Reduce resolution** — SDXL at 768px instead of 1024px saves meaningful VRAM.

```bash
python launch.py --medvram-sdp --xformers
```

`--xformers` (or `--flash-attention`) cuts memory and speeds up generation
substantially. Install `xformers` matching your torch version.

## Common failures

**Black images with FLUX** — fp16 on pre-Ampere. Use bf16, or GGUF.

**OOM at 1024×1024 on SDXL** — use Forge, or `--lowvram`, or `enable_model_cpu_offload()`.

**Images look like soup** — too few steps or wrong CFG for the model.

**LoRA has no effect** — the LoRA was trained for a different base model
(SD1.5 LoRA on an SDXL checkpoint does nothing), or the weight is too low.

**Slow generation** — missing `xformers` or `flash-attn`. Check the console
output; it says which attention implementation it selected.

**Same image every time** — the seed is fixed. Set `seed=-1` for random.

## Reference tools

Other open-source image tools worth knowing, each over 1,000
GitHub stars — see `references/image-reference-tools.md`.

## Related skills

`comfyui-image-workflows` · `comfyui-video-workflows` ·
`background-removal-segmentation` · `thumbnail-generator` ·
`text-to-video-local`
