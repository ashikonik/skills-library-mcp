# Music model comparison

| Model | Duration | Vocals | Licence | Strengths |
|---|---|---|---|---|
| MusicGen small | 30s | No | CC-BY-NC | Fast drafts |
| MusicGen medium | 30s | No | CC-BY-NC | Best instrumental |
| MusicGen large | 30s | No | CC-BY-NC | Best timbre |
| MusicGen 3.5B | 30s | No | CC-BY-NC | Stereo |
| AudioGen | 10s | SFX only | CC-BY-NC | Sound design |
| ACE-Step 1.5 | 4 min | Yes | MIT | Full songs, structure |
| YuE | 5 min | Yes | Apache-2.0 | Lyrics to song |
| Stable Audio Open | 47s | No | Non-commercial (code MIT) | Cinematic fidelity |

## Prompt formula

```
[GENRE] + [INSTRUMENTATION] + [TEMPO] + [MOOD] + [PRODUCTION]
```

Example:

```
cinematic orchestral trailer music, cello and piano, building tension,
120 bpm, dramatic, wide reverb
```

Avoid artist names and song titles.

## Generation parameters

| Parameter | Effect |
|---|---|
| `duration` | Seconds. 30 max for MusicGen. |
| `guidance_scale` | Prompt adherence. 2.0–3.5 is safe. Above 4 is harsh. |
| `temperature` | Variation between runs. 0.8–1.2. |
| `top_k` | 250 standard. Lower = more predictable. |
| `top_p` | 0.0 standard. |

## Mixing levels

| Element | LUFS |
|---|---|
| Narration | -16 |
| Music under narration | -22 to -26 |
| Music alone | -14 |
| True peak | -1.5 dBTP |

## Crossfading generated segments

```python
def crossfade(a, b, n):
    fade = torch.linspace(1, 0, n)
    return torch.cat([a[:-n], a[-n:] * fade + b[:n] * (1 - fade)])
```

2 seconds for ambient, 4 for percussive.
