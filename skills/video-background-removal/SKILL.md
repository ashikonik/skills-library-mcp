---
name: video-background-removal
description: Remove or replace backgrounds in video footage using local open-source tools — rembg with video support, MediaPipe Selfie Segmentation, Robust Video Matting, and FFmpeg chroma key — for green screen replacement, subject isolation, and compositing over new backgrounds. Use when the user wants to remove a video background, do green screen keying, cut out a subject from footage, or composite a person onto another background.
metadata:
  promptSignals:
    phrases:
      - remove video background
      - green screen
      - chroma key
      - cut out subject
      - video matting
      - background replacement video
      - remove.bg video
      - composite person onto background
---

# Video Background Removal

Same problem as image background removal, but the output must be **temporally
consistent** — if the matte flickers frame to frame, the result is unusable.

## Approach selection

| Approach | Quality | Speed | When to use |
|---|---|---|---|
| Green screen (chroma key) | Best | Real-time | You had a green screen at shoot time |
| Robust Video Matting (RVM) | Very good | Real-time | Real footage, person against background |
| MediaPipe Selfie | Good | Very fast | Quick preview, mobile-style |
| rembg (image-per-frame) | Good | Slow | Static subject, not much motion |

**If you shot with a green screen, key it.** Nothing AI-based matches a clean
chroma key, and it costs nothing.

## Green screen / chroma key with FFmpeg

```bash
ffmpeg -i input.mp4 \
  -vf "colorkey=0x00FF00:0.3:0.1,format=yuva420p" \
  -c:v libx264 -c:v libx264 -pix_fmt yuv420p \
  output_alpha.mp4
```

- `colorkey=0x00FF00` — the key colour. Sample yours; it is rarely pure green.
- `0.3` — similarity threshold. Raise it if background residue remains, lower
  it if the subject is getting holes.
- `0.1` — blend. Smooths the edge.

Then composite over a new background:

```bash
ffmpeg -i output_alpha.mp4 -i new_background.mp4 \
  -filter_complex "[0:v][1:v]overlay=shortest=1" \
  -c:v libx264 -crf 18 -pix_fmt yuv420p composited.mp4
```

**Better edges with a despill pass** — green fringing on hair is the classic
chroma-key failure:

```bash
ffmpeg -i input.mp4 \
  -vf "chromakey=0x00FF00:0.3:0.1,despill=type=green:amount=0.6,format=yuva420p" \
  -c:v libx264 -pix_fmt yuv420p alpha.mp4
```

## Robust Video Matting (best AI quality for real footage)

[RVM](https://github.com/PeterL1n/RobustVideoMatting) produces temporally
consistent mattes. This is the best open option for a person against a busy
background.

```bash
git clone https://github.com/PeterL1n/RobustVideoMatting.git
cd RobustVideoMatting
pip install -r requirements.txt
python inference_video.py \
  --input ../input.mp4 \
  --output ../output.mp4 \
  --matting_mode 1 \
  --fps 25 \
  --trimap 20
```

- `--matting_mode 1` — "robust" mode, best quality.
- `--trimap 20` — trimap radius. Lower is faster; higher catches more hair
  detail.
- `--fps` — **match the source frame rate exactly**. Mismatched fps is the
  most common cause of output that looks sped up or stuttered.

Then composite the alpha over a background:

```bash
ffmpeg -i output.mp4 -i bg.mp4 \
  -filter_complex "[0:v][1:v]overlay=shortest=1" \
  -c:v libx264 -crf 18 -pix_fmt yuv420p final.mp4
```

## MediaPipe Selfie Segmentation (fast preview)

```python
import cv2, mediapipe as mp

seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)
cap = cv2.VideoCapture("input.mp4")
fps = cap.get(cv2.CAP_PROP_FPS)

out = cv2.VideoWriter("output.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps,
                       (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))

while cap.isOpened():
    ok, frame = cap.read()
    if not ok: break
    r = seg.process(frame)
    mask = r.segmentation_mask
    out.write(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR))

out.release()
```

`model_selection=1` is the full model; `0` is the fast one. This writes a mask
video, not a cut-out — composite it separately.

## rembg for image-per-frame

Works when the subject does not move much. Slow, but the quality is good.

```bash
pip install rembg[gpu]
# process a frame sequence
for f in frames/*.png; do
  rembg -i "$f" -o "cut/${f##*/}" -m u2net_human_seg
done
```

`-m u2net_human_seg` is the model tuned for people. Other options:
`u2net`, `isnet-general-use`, `birefnet-general`.

## Temporal consistency

The failure mode that matters. A matte that is perfect on frame 100 and flickers
on frame 101 reads as broken.

**Why it happens:**
- Independent per-frame segmentation with no temporal model.
- Wrong frame rate on the output, so frames get duplicated or dropped.
- Motion blur in the source — the matte cannot recover detail that was smeared.

**Fixes:**
1. Use a model with temporal consistency (RVM, not per-frame rembg).
2. Match `--fps` to the source exactly.
3. If the source has motion blur, no matte model fixes it — reshoot or pick a
   different shot.
4. Slight temporal smoothing on the mask helps hide single-frame errors.

## Composite onto a new background

```bash
ffmpeg -i alpha.mp4 -i background.mp4 \
  -filter_complex "[1:v][0:v]overlay=shortest=1:format=auto" \
  -c:v libx264 -crf 18 -pix_fmt yuv420p out.mp4
```

Or in Python for more control (blur the background, add a gradient):

```python
import cv2, numpy as np

fg = cv2.VideoCapture("alpha.mp4")
bg = cv2.VideoCapture("background.mp4")
out = cv2.VideoWriter("out.mp4", cv2.VideoWriter_fourcc(*"mp4v"), 25, (1920, 1080))

while True:
    ok_f, f = fg.read()
    ok_b, b = bg.read()
    if not (ok_f and ok_b): break
    h, w = f.shape[:2]
    b = cv2.resize(b, (w, h))
    # optional: blur the background behind the subject
    blurred = cv2.GaussianBlur(b, (0, 0), 18)
    mask = f[:, :, 3:4] / 255.0
    blended = (f[:, :, :3] * mask + blurred * (1 - mask)).astype(np.uint8)
    out.write(blended)
```

## Common failures

**Holes in the subject** — the key colour tolerance is too tight, or the
subject contains shades close to the key colour. Widen the threshold.

**Green fringe on hair** — no despill pass. Add `despill=type=green`.

**Output plays too fast** — `--fps` did not match the source.

**Black background instead of transparent** — the alpha channel was dropped.
`format=yuva420p` preserves it; `format=yuv420p` discards it.

**Segmentation captures the background** — the model is `u2net` rather than
`u2net_human_seg`, or the shot contains other people.

**Alpha channel lost in the final encode** — encode with a codec that keeps
alpha (`VP9` in WebM, ProRes 4444, or PNG sequence), or composite before
encoding.

## Related skills

`background-removal-segmentation` · `media-transcode-pipeline` ·
`shorts-reels-pipeline` · `lip-sync` · `video-translation-dubbing`
