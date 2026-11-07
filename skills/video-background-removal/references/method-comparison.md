# Background removal methods

| Method | Real-time | Quality | Handles hair | Needs a green screen |
|---|---|---|---|---|
| Chroma key | Yes | Perfect | No | Yes |
| Robust Video Matting | No | Excellent | Yes | No |
| MediaPipe Selfie | Yes | Good | No | No |
| rembg per frame | No | Good | No | No |
| SAM 2 | No | Good (masks) | No | No |

## Chroma key — only when you control the background

```bash
ffmpeg -i in.mp4 -vf "chromakey=0x00FF00:0.3:0.1" -c:v libx264 -crf 18 out.mp4
```

Colour similarity 0.3, blend 0.1. Despill after:

```bash
ffmpeg -i out.mp4 -vf "despill=type=green:mix=0.5" despilled.mp4
```

## Robust Video Matting — the best general option

```python
from rvm import RobustVideoMatting
import torch

model = RobustVideoMatting().eval()
frames = read_frames("in.mp4")

output = []
for frame in frames:
    f = torch.from_numpy(frame).float() / 255.0
    f = f.permute(2, 0, 1).unsqueeze(0)
    pha, fgr = model(f, 0.5, 0.25)      # rec, downsampling
    output.append((fgr[0].numpy(), pha[0].numpy()))

write_rgba("out.mov", output)
```

## Temporal consistency

Per-frame methods flicker because each frame is independent. Fixes:

1. **Optical-flow propagation** — SAM 2's video mode propagates the mask
   through the sequence.
2. **Temporal smoothing** — average the alpha channel over a short window.
3. **Morphological cleanup** — opening then closing removes speckle.

```python
import cv2
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, kernel)
alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)
```

## Compositing

```bash
ffmpeg -i keyed.mov -i background.mp4 \
  -filter_complex "[0:v][1:v]overlay=0:0" \
  -c:v libx264 -crf 18 -c:a copy composited.mp4
```

ProRes 4444 with alpha is the safest intermediate if you will composite in
an editor.
