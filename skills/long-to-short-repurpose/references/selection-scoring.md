# Highlight selection scoring

## Signal weights

| Signal | Weight | Rationale |
|---|---|---|
| Number or statistic | +3 | Concrete claims hook |
| Question | +2 | Curiosity gap |
| Emotional language | +2 | Strong opinions perform |
| Conclusion marker | +2 | Self-contained ending |
| First sentence of segment | +1 | Often a topic sentence |
| Starts mid-sentence | -3 | Confusing without context |
| Contextual referral | -3 | Needs prior context |

## Regexes

```python
import re

NUMBERS = re.compile(r"\b\d+(\.\d+)?%?\b")
QUESTIONS = re.compile(r"\?")
EMOTIONAL = re.compile(
    r"\b(never|always|worst|best|mistake|wrong|secret|actually|huge|amazing)\b", re.I)
CONCLUSION = re.compile(
    r"\b(so the point is|that's why|the takeaway|in summary|basically)\b", re.I)
CONTEXT_DEP = re.compile(
    r"\b(as I said|like before|earlier|again|as mentioned)\b", re.I)
```

## Duration distribution

Vary the durations across a batch. Identical lengths read as machine-made.

| Length | Use for |
|---|---|
| 15-25s | A single sharp point |
| 25-40s | A punchy argument |
| 40-60s | A story with a turn |
| 60-90s | A complete explanation |

## Scene-change density

```bash
ffmpeg -i long.mp4 -filter:v "select='gt(scene,0.3)',showinfo" \
  -f null - 2>&1 | grep showinfo | grep pts_time
```

A candidate with scene changes every 4–8 seconds has visual interest. A
candidate with no scene changes is a talking head — only worth taking if
the words are strong.

## Cutting on word boundaries

Use whisper's word timestamps to snap cuts:

```python
def snap_to_word(words, target, tolerance=0.4):
    best = min(words, key=lambda w: abs(w.start - target))
    if abs(best.start - target) <= tolerance:
        return best.start - 0.15   # small pre-pad
    return target
```
