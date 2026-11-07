---
name: comfyui-image-workflows
description: Build and run ComfyUI workflows for image generation and editing — SDXL, SD 1.5, Flux, ControlNet, IPAdapter, inpainting, upscaling, and IPAdapter Plus — including workflow JSON authoring, model placement, and the headless API for batch generation. Use when the user works with ComfyUI graphs for images, wants to automate image generation, or needs reproducible image pipelines.
metadata:
  promptSignals:
    phrases:
      - comfyui image workflow
      - comfyui graph image
      - automate image generation
      - sdxl comfyui
      - controlnet comfyui
      - ipadapter comfyui
      - inpainting workflow
      - comfyui batch image
      - flux comfyui
---

# ComfyUI Image Workflows

ComfyUI for images is a graph: a checkpoint, a text encoder, a sampler, a VAE.
For editing you add conditioning branches instead of just a prompt.

## Model placement

```
ComfyUI/models/
├── checkpoints/    .safetensors  (SD1.5, SDXL, Flux)
├── unet/           .safetensors  (Flux, Hunyuan — separate UNet weights)
├── vae/            .safetensors
├── clip/           .safetensors  (SDXL's separate CLIP-L)
├── clip_vision/    .safetensors  (for IPAdapter)
├── controlnet/     .safetensors
├── loras/          .safetensors
├── style_models/   .safetensors  (IPAdapter style)
└── upscale_models/ .pth
```

SDXL checkpoints go in `checkpoints/`. Flux needs **three** files — the main
weights in `checkpoints/`, the UNet in `unet/`, and the CLIP in `clip/`. Missing
the `unet/` file is the most common Flux setup error.

## Core graph

```
CheckpointLoaderSimple ──┬─→ MODEL ──────→ KSampler ──→ VAEDecode ──→ SaveImage
                          ├─→ CLIP ──→ CLIPTextEncode (+) ──→ KSampler.positive
                          │         └─→ CLIPTextEncode (−)
                          └─→ VAE ──────────────────────→ (for VAEEncode)
```

For SDXL, `CheckpointLoaderSimple` already includes both CLIPs. For Flux, use
`UNETLoader` + `DualCLIPLoader` + `VAELoader` instead.

## ControlNet

A ControlNet branch feeds structural conditioning (canny edges, depth, pose,
segmentation) alongside the text prompt.

```
ControlNetLoader ──→ Apply ControlNet (advanced) ──→ KSampler
                                                       ↑
LoadImage → ControlNetPreprocessor (Canny/Depth/Pose) ─┘
```

Preprocessor nodes: `Canny`, `DepthAnything`, `OpenPose`, `Lineart`, `Midas`,
`Segmentation`. The preprocessor and the ControlNet model must agree — a
depth ControlNet with a canny preprocessor produces nonsense.

## IPAdapter (style / reference image)

Lets you condition on a reference image without training.

```
LoadImage → CLIPVisionLoader → IPAdapterModelLoader → IPAdapterAdvanced ──→ KSampler
```

`IPAdapterAdvanced` has weight, weight_type, and start/end_at. For style
transfer, use `weight_type: "style"` and the `PLUS` model. For composition
transfer, use `weight_type: "composition"` with `weight: 1.0`.

Style and composition are mutually exclusive in IPAdapter Plus — pick one.

## Inpainting

```
LoadImage → VAEEncode → (add noise via KSampler with denoise < 1.0)
```

For a masked inpaint, use `InpaintModelConditioning` (SD1.5/SDXL) which takes
the image and a mask and produces the conditioning directly.

`denoise` controls how much of the original is replaced:
- `0.3` — light touch, keeps most structure
- `0.5` — moderate, blends original and new
- `0.8` — mostly new content
- `1.0` — full regenerate within the mask

## Headless API

```python
import json, uuid, time, urllib.request

HOST = "http://127.0.0.1:8188"

def queue(workflow):
    body = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{HOST}/prompt", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["prompt_id"]

def wait(prompt_id, timeout=600):
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{HOST}/history/{prompt_id}") as r:
            hist = json.loads(r.read())
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(1)
    raise TimeoutError(prompt_id)

def collect(prompt_id):
    """Download every image produced by a completed prompt."""
    hist = wait(prompt_id)
    out = []
    for node_out in hist.get("outputs", {}).values():
        for img in node_out.get("images", []):
            url = f"{HOST}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img.get('type','output')}"
            with urllib.request.urlopen(url) as r:
                out.append(r.read())
    return out
```

**Use the API format JSON**, not the GUI format. In the UI: *Save (API Format)*.
The GUI format includes node positions and no `class_type` mapping — the API
rejects it.

## Batch generation

```python
import json

base = json.load(open("workflows/sdxl_api.json"))
PROMPT_NODE = "6"
NEG_NODE = "7"
SAMPLER = "3"

images = []
for i, (prompt, seed) in enumerate(prompts):
    wf = json.loads(json.dumps(base))   # deep copy
    wf[PROMPT_NODE]["inputs"]["text"] = prompt
    wf[NEG_NODE]["inputs"]["text"] = negative
    wf[SAMPLER]["inputs"]["seed"] = seed
    images += collect(queue(wf))

open("output/contact_sheet.jpg", "wb").write(make_sheet(images))
```

Vary the **seed**, not the prompt, when you want the same composition with
different details. Vary the prompt only when you want a different composition.

## Upscaling in-graph

```
LoadImage → ImageUpscaleWithModel → SaveImage
```

Models in `models/upscale_models/`. `4x-UltraSharp` for photos,
`4x_NMKD-Siax` for general use, `RealESRGAN_x4plus` for photographic detail.

For tiled upscaling of large images, use the `Ultimate SD Upscale` node chain
instead — it tiles internally and avoids the VRAM wall.

## Common failures

**"Checkpoint not found"** — the file is in the wrong subdirectory, or ComfyUI
needs a restart to rescan `models/`.

**Flux produces noise** — the UNet file is missing from `models/unet/`. Flux
needs the split weights.

**ControlNet ignored** — the preprocessor output and ControlNet model do not
match, or the ControlNet weight is too low.

**IPAdapter makes everything look the same** — you used the wrong
`weight_type`. Use `style` for style, `composition` for layout.

**Out of memory on SDXL** — enable `--lowvram`, or use `Common Diffusion
Sampler` with a resolution-aware split.

**Black or flat images** — the VAE is fp16 on hardware where fp16 VAE is
unstable. Set the VAE to `bf16` or run the VAE in fp32.

## Reference tools

Other open-source image tools worth knowing, each over 1,000
GitHub stars — see `references/image-reference-tools.md`.

## Related skills

`local-diffusion-suite` · `comfyui-video-workflows` ·
`background-removal-segmentation` · `thumbnail-generator` · `text-to-video-local`
