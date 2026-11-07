---
name: long-to-short-repurpose
description: Extract short-form clips from long-form video — detecting highlight moments, scoring for virality, generating vertical reframing with speaker tracking, adding hook captions, and batch producing shorts from a podcast or long video. Use when the user wants to repurpose a long video into shorts, find highlights in a podcast, or make vertical clips from landscape footage.
metadata:
  promptSignals:
    phrases:
      - repurpose long video
      - extract highlights
      - turn podcast into shorts
      - find the best moments
      - make clips from a video
      - vertical reframing
      - auto clip video
      - social clips
---

# Long to Short Repurposing

Turning one long video into a set of short vertical clips. The value is in
selection — a clip nobody watches is worse than no clip.

## The selection problem

Picking 30–90 seconds out of 40 minutes. You need **moments that work without
context**. A good short:

- Makes sense with zero prior knowledge
- Has a clear payoff in the first 3 seconds
- Ends on a conclusion, not mid-sentence
- Contains something worth reacting to

## Method 1 — Transcript-based scoring

Transcribe, then score segments.

```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, _ = model.transcribe("long.mp4", vad_filter=True,
                               word_timestamps=True)

# write a review file
with open("transcript.txt", "w") as f:
    for seg in segments:
        f.write(f"[{seg.start:8.2f} → {seg.end:8.2f}] {seg.text.strip()}\n")
```

Then score by signals:

| Signal | Weight | Why |
|---|---|---|
| Contains a number or statistic | +3 | Concrete claims hook |
| Contains a question | +2 | Curiosity |
| Emotional language ("never", "always", "worst", "best") | +2 | Strong opinions perform |
| First sentence of a segment | +1 | Often a summary or topic sentence |
| Contains a conclusion ("so", "that's why", "the point is") | +2 | Self-contained ending |
| Starts mid-sentence | −3 | Confusing without context |
| Contains a referral ("as I said", "like before") | −3 | Needs context |

```python
import re

NUMBERS = re.compile(r"\b\d+(\.\d+)?%?\b")
QUESTIONS = re.compile(r"\?")
EMOTIONAL = re.compile(r"\b(never|always|worst|best|mistake|wrong|secret|actually|huge|amazing)\b", re.I)
CONCLUSION = re.compile(r"\b(so the point is|that's why|the takeaway|in summary|basically)\b", re.I)
CONTEXT_DEP = re.compile(r"\b(as I said|like before|earlier|again|as mentioned)\b", re.I)

def score(seg_text, is_start=False):
    s = 0
    if NUMBERS.search(seg_text): s += 3
    if QUESTIONS.search(seg_text): s += 2
    if EMOTIONAL.search(seg_text): s += 2
    if CONCLUSION.search(seg_text): s += 2
    if CONTEXT_DEP.search(seg_text): s -= 3
    if is_start: s -= 2
    return s
```

Then greedily select non-overlapping windows of 30–90 seconds.

## Method 2 — Visual-based highlight detection

A great audio moment with a boring visual is not a clip. Detect visual peaks.

```bash
# scene changes
ffmpeg -i long.mp4 -filter:v "select='gt(scene,0.3)',showinfo" \
  -f null - 2>&1 | grep showinfo | grep pts_time
```

```python
import subprocess, re

def scene_changes(path, threshold=0.3):
    out = subprocess.run(
        ["ffmpeg", "-i", path, "-filter:v",
         f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    times = [float(m) for m in re.findall(r"pts_time:([\d.]+)", out)]
    return sorted(times)
```

Combine with audio energy to find moments where **both** something visual and
something verbal happened:

```python
import numpy as np, librosa

y, sr = librosa.load("audio.wav", sr=22050)
rms = librosa.feature.rms(y=y)[0]
threshold = np.percentile(rms, 75)
loud_moments = [i / 22050 for i, v in enumerate(rms) if v > threshold]
```

Score a candidate clip by scene-change density plus loudness.

## Method 3 — Let a model find them

```bash
pip install auto-editor
auto-editor long.mp4 --edit "all" -o cut.mp4
auto-editor long.mp4 --edit "audio:threshold=0.04" -o cut_silence.mp4
```

`auto-editor` removes silence and, with `--edit "all"`, detects motion. Useful as
a first pass before human selection.

```bash
# also available: jumpcutter-style tools
pip install jumpcutter
```

## Vertical reframing

Landscape 16:9 → vertical 9:16 without cropping the subject out of frame.

**Speaker tracking** is the key. Use a face detector to follow the active
speaker and pan a virtual crop.

```bash
# crop with a fixed centre (works when the speaker stays centred)
ffmpeg -i long.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
  -c:v libx264 -crf 18 -c:a copy vertical.mp4
```

For tracked reframing, extract per-frame face positions with MediaPipe, then
build a crop filter:

```python
import cv2, json, subprocess

# 1. detect faces per frame
cap = cv2.VideoCapture("long.mp4")
tracker = ...   # MediaPipe face detection
tracks = []
while True:
    ok, frame = cap.read()
    if not ok: break
    box = detect_active_speaker_box(frame)
    tracks.append(box)
cap.release()

# 2. smooth the crop path (raw detection jitters)
import numpy as np
s = np.array([t["cx"] for t in tracks], dtype=float)
kernel = np.ones(15) / 15
s = np.convolve(s, kernel, mode="same")

# 3. write the crop filter
expr = []
for i, x in enumerate(s):
    expr.append(f"crop=1080:1920:{max(0,int(x-540))}:0")
print(":".join(expr[:200]))
```

Then apply:

```bash
ffmpeg -i long.mp4 -vf "<crop_expr>" -c:v libx264 -crf 18 -c:a copy vertical.mp4
```

**Smoothing is not optional.** Raw per-frame detection produces a shaky crop
that is worse than a static centre crop.

If the video is a podcast with a fixed camera, **static centre crop is usually
better** than tracked reframing.

## Adding a hook

The clip's first 3 seconds decide whether it is watched. Add a hook caption.

```python
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def load_font(size):
    """DejaVu Sans Bold, wherever the distro put it."""
    for p in (
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",             # Debian/Ubuntu, Arch
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # older Debian
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",           # Fedora
        "/Library/Fonts/Arial Bold.ttf",                         # macOS
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.truetype("DejaVuSans-Bold.ttf", size)

def add_hook(video_path, out_path, text, duration=2.5):
    font = load_font(84)
    # build an ASS file with the hook as an overlay for the first N seconds
    ...
```

Better: burn it as an overlay clip, then concatenate.

```bash
# hook overlay for the first 2.5s
ffmpeg -i clip.mp4 -f lavfi -i "color=c=black@0.0:s=1080x1920:d=2.5" \
  -filter_complex "[0:v][1:v]overlay=0:0:enable='between(t,0,2.5)'" \
  -c:v libx264 -crf 18 -c:a copy with_hook.mp4
```

For text, use the `drawtext` filter or an ASS subtitle — see
`subtitle-generation`.

## Batch production

```python
import json, subprocess, os

os.makedirs("clips", exist_ok=True)
for clip in selected:
    out = f"clips/clip_{clip['start']:.0f}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", f"{clip['start']:.2f}", "-i", "long.mp4",
        "-t", f"{clip['duration']:.2f}",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v", "libx264", "-crf 20 -preset fast",
        "-c:a", "aac", "-b:a 128k",
        out,
    ], check=True)
```

`-ss` **before** `-i` is fast seeking (keyframe-based). `-ss` after `-i` is
accurate but slow. For frame-accurate cuts use the slow form, then trim to the
exact frame with a second pass.

## Common failures

**Clips need context** — the selection included referential language. Filter
with the context-dependence regex.

**The subject is cropped out** — the speaker is off-centre. Use tracked
reframing, or reframe in the edit.

**The crop shakes** — detection was not smoothed. Apply a moving average.

**Clips are all the same length and feel mechanical** — vary the durations.
Short punchy clips (20–40s) usually outperform the full 90s.

**Audio starts mid-word** — cut on a silence boundary. Use whisper's word
timestamps to snap the cut to a word boundary plus a small pad.

**Copyright on the source** — you need the rights to the original footage.
Repurposing your own content is fine; reposting someone else's is not.

## Related skills

`subtitle-generation` · `shorts-reels-pipeline` · `thumbnail-generator` ·
`stock-media-sourcing` · `tts-to-video` · `media-transcode-pipeline` ·
`social-publish-scheduling`
