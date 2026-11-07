---
name: background-removal-segmentation
description: Remove backgrounds from images and segment subjects using local open-source tools — rembg with BiRefNet and U²-Net models, IOPaint for inpainting, SAM 2 for promptable segmentation, and alpha matting for hair detail. Use when the user wants to remove an image background, cut out an object, make a transparent PNG, or segment a subject from a photo.
metadata:
  promptSignals:
    phrases:
      - remove image background
      - background removal
      - transparent png
      - cut out object
      - segment image
      - rembg
      - birefnet
      - sam 2 segmentation
      - iopaint
      - remove.bg alternative
---

# Image Background Removal and Segmentation

Removing a background is two problems: **detect** the subject, and **produce a
clean edge**. Most bad results are an edge problem, not a detection problem.

## Tool selection

| Tool | Repo | Best for |
|---|---|---|
| **rembg** | `danielgatis/rembg` | One-command subject cutout. Best default. |
| **IOPaint** | `Sanster/IOPaint` | Inpainting and object removal after segmentation |
| **SAM 2** | `facebookresearch/sam2` | Promptable segmentation ("the dog", "the sign") |
| **Segment Anything** | `facebookresearch/segment-anything` | SAM 1, still useful |
| **BiRefNet** | `ZhengPeng7/BiRefNet` | High-quality matting model, used by rembg |
| **ImageToolbox** | `T8RIN/ImageToolbox` | GUI for all of the above, batch capable |

## rembg

```bash
pip install rembg[gpu]
```

The CLI is `rembg <command> <input> <output>` — input and output are positional
arguments, and the subcommand selects the mode.

```bash
# single file, default model
rembg i input.jpg output.png

# best edge quality
rembg i -m birefnet-general input.jpg output.png

# people specifically
rembg i -m u2net_human_seg portrait.jpg portrait.png

# batch a directory
rembg p input_dir/ output_dir/

# keep the alpha channel clean on hair
rembg i -a input.jpg output.png
```

**Model choice matters more than any setting:**

| Model | Use for |
|---|---|
| `birefnet-general` | Best overall edge quality. Try this first. |
| `birefnet-general-lite` | Faster, slightly softer edges |
| `bria-rmbg` | The default; fast and good, licence-free for non-commercial use |
| `u2net_human_seg` | People, portraits |
| `u2net` | General objects |
| `isnet-general-use` | Alternative general model, good with clutter |
| `silueta` | Small, fast, rough |

```python
from rembg import remove, new_session

session = new_session("birefnet-general")
with open("input.jpg", "rb") as f:
    data = f.read()
result = remove(data, session=session, alpha_matting=True,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10)
open("output.png", "wb").write(result)
```

`alpha_matting=True` is what recovers **hair and fur detail**. It is slower and
can eat thin structures if the thresholds are off. If the result has holes in
hair, raise `foreground_threshold`; if the background is leaking, raise
`background_threshold`.

## SAM 2 for promptable segmentation

When you know *what* to cut out but not where it is:

```bash
pip install git+https://github.com/facebookresearch/sam2.git
```

```python
import torch
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

predictor = SAM2ImagePredictor.from_pretrained(
    "facebook/sam2.1-hiera-large", model_cfg=None)
predictor.set_image("input.jpg")

masks, scores, logits = predictor.predict(
    point_coords=[[450, 300]],          # click point
    point_labels=[1],                   # 1 = foreground
    multimask_output=True)
best = masks[scores.argmax()]
```

SAM 2 gives you a **binary mask**, not an alpha matte. For a clean cutout, feed
the mask through rembg's matting, or refine it with `IOPaint`.

## IOPaint for inpainting and object removal

Once you have a mask, IOPaint can fill it — remove an object, or inpaint a
background.

```bash
pip install iopaint
iopaint start --model=lama --device=cuda --port=8080   # web UI on :8080
```

Headless batch mode — `run` takes `--image`, `--mask`, and `--output`, all of
which accept **either a single file or a directory**:

```bash
# remove an object using a mask
iopaint run --model=lama --device=cuda \
  --image=input.jpg --mask=mask.png --output=clean.jpg

# batch: one mask per image, matching filenames in the same folder
iopaint run --model=lama --device=cuda \
  --image=images/ --mask=masks/ --output=results/
```

`--concat` writes a side-by-side of original, mask, and result — useful for
spot-checking a batch. Other subcommands: `iopaint list` (models already
downloaded), `iopaint download <hf-model-id>`, and
`iopaint install-plugins-packages`.

Models: `lama` (fast, general), `lama_fp16` (faster), `sd2` (Stable Diffusion
inpainting), `migan`, `aot`. Any SD/SDXL inpainting model on Hugging Face
also works — pass the repo id to `--model`.

> **Note:** `Sanster/IOPaint` was archived in April 2025. The package still
> installs and works, but it no longer receives upstream fixes. For new
> projects prefer `rembg` for cutouts and `diffusers`' inpainting pipelines
> for fills.

## Alpha matting by hand

When rembg's built-in matting is not enough:

```python
from pymatting import estimate_alpha_cf
from PIL import Image
import numpy as np

foreground = np.array(Image.open("cutout.png").convert("RGBA"))
trimap = np.array(Image.open("trimap.png"))   # 0=bg, 128=unknown, 255=fg

alpha = estimate_alpha_cf(foreground, trimap)
Image.fromarray((alpha * 255).astype(np.uint8)).save("alpha.png")
```

## Producing a clean composite

```python
from PIL import Image

bg = Image.open("background.jpg").convert("RGBA")
fg = Image.open("cutout.png").convert("RGBA")

# scale fg to 80% and place
fg = fg.resize((int(fg.width * 0.8), int(fg.height * 0.8)))
bg.alpha_composite(fg, (int((bg.width - fg.width) / 2), int((bg.height - fg.height) / 2)))
bg.convert("RGB").save("composite.jpg", quality=95)
```

For a background removal API in a pipeline, `rembg`'s Python API is the fastest
path.

## Common failures

**Holes in the subject** — alpha matting is too aggressive. Raise
`alpha_matting_foreground_threshold` from 240 toward 250, or turn matting off.

**Background leaking through hair** — matting is off, or the background is
similar in colour to the subject. Turn `alpha_matting=True` on.

**Object not removed** — the mask is wrong. Generate it with SAM 2 using an
explicit click rather than rembg's automatic detection.

**Subject cut off at the edges** — the subject touches the image border, so the
model cannot see its full extent. Pad the image before processing.

**Transparent PNG has a black background when viewed** — the viewer does not
support alpha. Check with `Image.open(out).mode == "RGBA"`.

**Inpaint produces a blurry patch** — the `lama` model is doing its job; it is
good at smooth backgrounds and bad at detailed ones. Use `sd2` for complex
backgrounds.

## Reference tools

Other open-source image tools worth knowing, each over 1,000
GitHub stars — see `references/image-reference-tools.md`.

## Related skills

`comfyui-image-workflows` · `video-background-removal` · `local-diffusion-suite` ·
`thumbnail-generator`
