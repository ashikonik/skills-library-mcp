# Building a timing map

The timing map is what lets you place visuals against the right words. Build
it from the actual generated audio, never from an estimate.

```python
import wave, glob

def durations(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()

def build_timing_map(pattern="vo/seg_*.wav", gap=0.35):
    segments = []
    offset = 0.0
    for path in sorted(glob.glob(pattern)):
        d = durations(path)
        segments.append({"path": path, "start": offset,
                         "end": offset + d, "duration": d})
        offset += d + gap
    return segments, offset
```

## Beat planning

```python
import re

def beats(text, max_chars=180):
    parts = re.split(r"(?<=[.!?])\s+", text)
    out, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 1 > max_chars and cur:
            out.append(cur.strip())
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur.strip())
    return out
```

## Visual density

| Narration length | Visual |
|---|---|
| < 2s | Single establishing shot or B-roll |
| 2-5s | One visual, may move within frame |
| 5-10s | Two visuals, or one with a cutaway |
| > 10s | Multiple visuals, or a visual with an overlay |

## Padding is what prevents drift

```python
c = VideoFileClip(path)
c = c.subclipped(0, min(c.duration, seg["duration"]))
if c.duration < seg["duration"]:
    c = c.with_duration(seg["duration"])   # <-- the critical line
```

Without `with_duration`, the clip's actual duration wins and the narration
desynchronises by the second clip.

## Ducking

```bash
ffmpeg -i music.wav -i vo.wav -filter_complex \
  "[0:a][1:a]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[ducked];\
   [1:a][ducked]amix=inputs=2:duration=first:weights=1 0.5" mixed.wav
```
