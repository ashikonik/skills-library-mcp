---
name: thumbnail-generator
description: Generate thumbnails for videos and articles that get clicked — local image generation for the base image, compositing text overlays with Pillow, A/B variants, platform aspect ratios, and the visual rules that make a thumbnail legible at small sizes. Use when the user wants a YouTube thumbnail, article cover image, social preview card, or wants to A/B test thumbnail designs.
metadata:
  promptSignals:
    phrases:
      - make a thumbnail
      - youtube thumbnail
      - thumbnail design
      - article cover image
      - social preview card
      - click through image
      - thumbnail text overlay
      - a/b test thumbnails
---

# Thumbnail Generation

A thumbnail has one job: get clicked at **200 pixels wide**. That constraint
drives every decision — text must be enormous, faces must be large, contrast must
be extreme. A beautiful thumbnail at full resolution that becomes illegible
small is a bad thumbnail.

## The three-second test

Squint at the thumbnail until it blurs. If you cannot tell what it is about,
it fails. If the text is unreadable, it fails.

## Structure

Most high-performing thumbnails are one of:

```
┌─────────────────────────┐
│                         │
│   [LARGE SUBJECT]       │   ← face or object, filling 40-60%
│         ┌───────────┐   │
│  ┌──────┤  TEXT     │   │   ← 3-5 words, high contrast
│  │      └───────────┘   │
│                         │
└─────────────────────────┘
```

1. **Background** — high contrast against the subject. Dark subject → light
   background and vice versa.
2. **Subject** — a face with a clear expression, or a recognisable object. Crop
   tight: head and shoulders filling most of the frame.
3. **Text** — 3 to 5 words maximum. 2 words is better than 4.

## Generating the base image

```bash
# local diffusion
python - <<'PY'
import torch
from diffusers import StableDiffusionXLPipeline

pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16, variant="fp16").to("cuda")
pipe.safety_checker = None

prompt = ("close-up portrait of a surprised man with wide eyes, looking at "
          "camera, bold flat yellow background, high contrast, studio lighting, "
          "centered, sharp focus")
img = pipe(prompt, num_inference_steps=30, guidance_scale=7.0,
           width=1280, height=720).images[0]
img.save("base.png")
PY
```

**Put the background in the prompt, not behind the subject.** Asking a diffusion
model for "close-up portrait on a solid yellow background" gives a cleaner
result than generating a portrait and compositing a background yourself.

Negative prompt:

```
blurry, lowres, text, watermark, multiple people, distorted face, bad anatomy
```

Avoid asking for text in the image — diffusion models render text badly. Add
text with Pillow.

## Compositing text

```python
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def load_font(size):
    """DejaVu Sans Bold, wherever the distro put it."""
    candidates = [
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",        # Debian/Ubuntu, Arch
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # older Debian
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",      # Fedora
        "/Library/Fonts/Arial Bold.ttf",                    # macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    # last resort: let fontconfig resolve it
    return ImageFont.truetype("DejaVuSans-Bold.ttf", size)

W, H = 1280, 720
img = Image.open("base.png").convert("RGB").resize((W, H))

font = load_font(96)

draw = ImageDraw.Draw(img)
text = "THIS CHANGED EVERYTHING"

# draw a solid bar behind the text for legibility
bbox = draw.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
pad = 20
bar = (60, 60 - th // 2, 60 + tw + pad * 2, 60 + th + pad * 2)

draw.rectangle(bar, fill=(255, 0, 0))
draw.text((60 + pad, 60 + pad // 2), text, font=font, fill=(255, 255, 255))

img.save("thumb.jpg", quality=95)
```

**Do not hard-code one font path.** `/usr/share/fonts/truetype/dejavu/` is the
old Debian layout; current Debian/Ubuntu and Arch use `/usr/share/fonts/TTF/`,
Fedora uses `/usr/share/fonts/dejavu/`, and macOS has no DejaVu at all. Check
with `fc-list | grep -i dejavu` before assuming a path.

## Legibility rules

| Rule | Value |
|---|---|
| Word count | 3–5 (2 is fine) |
| Font size | 80–130px at 1280×720 |
| Font weight | Bold or Black |
| Text area | ≤ 25% of the frame |
| Contrast | White text on a solid dark bar, or black on a solid light bar |
| Stroke | 4–8px black outline if there is no bar |

A solid bar behind text is more reliable than an outline — it guarantees
contrast no matter what the image does underneath.

## Aspect ratios

| Target | Size |
|---|---|
| YouTube thumbnail | 1280×720 (16:9) |
| YouTube Short / Reel cover | 1080×1920 (9:16) |
| Instagram feed | 1080×1350 (4:5) |
| Blog / OG image | 1200×630 (1.91:1) |
| TikTok cover | 1080×1920 (9:16) |
| X / Twitter card | 1600×900 (16:9) |

Generate at the native resolution of the target — do not crop a 16:9 render to
9:16, you will lose the subject.

## A/B variants

Produce 3 variants and pick by eye (or by test). Vary one axis at a time:

- **Text** — different words, same image
- **Image** — same text, different subject expression
- **Colour** — different bar colour
- **Layout** — text top-left vs bottom-left

```python
from PIL import Image, ImageDraw, ImageFont

def make_variant(base, text, bar_color, position="bottom", H=720):
    img = base.copy()
    draw = ImageDraw.Draw(img)
    font = load_font(96)          # the helper defined above
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (60, H - th - 120) if position == "bottom" else (60, 60)
    draw.rectangle((x, y, x + tw + 40, y + th + 40), fill=bar_color)
    draw.text((x + 20, y + 20), text, font=font, fill=(255, 255, 255))
    return img
```

Vary the seed for a different face or expression — that is usually the biggest
lever on click-through.

## Thumbnail for an article cover

Different goal. No big text needed — the article title appears beside it.

- 1200×630
- Clean, editorial illustration or photo
- Text-safe area: the right third is usually covered by the title
- Avoid putting anything important in the outer 15% (cropped in feeds)

## Common failures

**Text unreadable at small size** — too many words, or the font is too small.
Cut words first, then grow the font.

**Face too small** — crop tighter. The face should be 30–50% of the frame height.

**Cluttered background** — competing with the subject. Blur it, or generate a
flat colour background.

**Subject blends into background** — invert the contrast relationship. Dark
subject, light background.

**Text looks like a different design than the video** — use the same font and
colour as the video's lower third.

**Platform crops the thumbnail** — YouTube crops to different aspect ratios on
mobile. Keep the subject centred and leave margin.

## Related skills

`local-diffusion-suite` · `comfyui-image-workflows` ·
`background-removal-segmentation` · `shorts-reels-pipeline` ·
`social-publish-scheduling` · `brand-discovery`
