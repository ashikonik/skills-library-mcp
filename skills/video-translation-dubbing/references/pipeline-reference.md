# Dubbing pipeline reference

## Order of operations

```
transcribe -> translate -> synthesize -> align -> [lip-sync] -> mix -> mux
```

Skipping alignment is the cause of nearly every dubbing failure.

## Language expansion factors

| Language | Expansion vs English |
|---|---|
| German | +30% |
| Finnish | +30% |
| French | +15% |
| Spanish | +15% |
| Japanese | -40% |
| Mandarin | -40% |
| Korean | -30% |

A German dub of an English line will not fit unless the translation is
tightened or the timing is stretched.

## atempo limits

`atempo` accepts 0.5-2.0 per instance. Chain for larger factors:

```python
def atempo_chain(factor):
    stages = []
    remaining = factor
    while remaining > 2.0:
        stages.append("atempo=2.0")
        remaining /= 2.0
    stages.append(f"atempo={remaining:.4f}")
    return ",".join(stages)
```

Beyond ±15% the speech sounds obviously synthetic. That is the practical
limit for the stretch-only approach.

## Mix levels

| Element | Level |
|---|---|
| Dub | -16 LUFS |
| Original bed (music, ambience) | -26 LUFS |
| True peak | -1.5 dBTP |

## Glossary format

```json
{
  "HunyuanVideo": "Video Hunyuan",
  "SDXL": "SDXL",
  "Sora": "Sora"
}
```

Protect each term with a placeholder before translating, then restore it
afterwards.

## Subtitle re-timing

```python
def retime(entry, cps_limit=17.0):
    chars = len(entry["text"].replace(" ", ""))
    dur = entry["end"] - entry["start"]
    if chars / dur <= cps_limit:
        return [entry]
    words = entry["text"].split()
    half = len(words) // 2
    mid = entry["start"] + dur * 0.5
    return [
        {**entry, "end": mid, "text": " ".join(words[:half])},
        {**entry, "start": mid, "text": " ".join(words[half:])},
    ]
```
