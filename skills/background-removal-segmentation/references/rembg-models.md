# rembg models

```bash
pip install "rembg[gpu]"
```

```python
from rembg import remove, new_session

session = new_session("u2net_human_seg")   # or "isnet-general-use"
out = remove("in.png", session=session)
```

| Model | Download | Best for |
|---|---|---|
| `u2net` | 168 MB | General objects |
| `u2net_human_seg` | 168 MB | People, portraits |
| `u2netp` | 4.4 MB | Low resource, poor edges |
| `isnet-general-use` | 170 MB | Best general quality |
| `birefnet-general` | 928 MB | Best edges, heaviest |
| `birefnet-portrait` | 928 MB | Portraits, hair |
| `birefnet-general-lite` | 214 MB | BiRefNet quality at a quarter of the size |
| `bria-rmbg` | 977 MB | The default model; strong on hard edges |
| `silueta` | 42 MB | Small, decent |

The BiRefNet models are large because they are the accurate ones. Start with
`birefnet-general-lite` (214 MB) if the download size matters more than the
last few percent of edge quality.

> `bria-rmbg` is BRIA's model and carries a non-commercial licence. Check its
> terms before shipping it in a product; `birefnet-general` has no such
> restriction.

## SAM 2 for promptable segmentation

```python
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

predictor = SAM2ImagePredictor(build_sam2("sam2_hiera_l.yaml"))
predictor.set_image("in.png")
masks, scores, _ = predictor.predict(
    point_coords=np.array([[x, y]]),
    point_labels=np.array([1]),
    multimask_output=True,
)
```

SAM 2 also has a video mode that propagates the mask through frames — this is
what fixes the flicker that per-frame methods produce.

## Alpha matting

A binary mask has hard edges. Matting refines the boundary:

```python
from pymatting import estimate_alpha_cf
alpha = estimate_alpha_cf(image, mask)
```

## Compositing

```python
from PIL import Image

fg = Image.open("cutout.png")
bg = Image.open("bg.jpg").convert("RGBA")
bg.alpha_composite(fg, (x, y))
bg.convert("RGB").save("composited.png")
```

## Inpainting instead of removal

```bash
pip install iopaint
iopaint run --model=lama --device=cuda \
  --image=in.png --mask=mask.png --output=out.png
```
