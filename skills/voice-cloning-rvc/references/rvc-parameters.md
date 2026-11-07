# RVC and voice conversion parameters

## The core distinction

**Cloning** — build a new voice model from a reference sample. The model
learns the speaker's timbre. Use GPT-SoVITS, XTTS, or OpenVoice.

**Conversion** — take an existing voice and map it onto a target speaker's
timbre. The emotion and timing of the source is preserved. Use RVC or
So-VITS-SVC.

## RVC key parameters

| Parameter | Range | Effect |
|---|---|---|
| `index_rate` | 0.0–1.0 | Feature retention. 0.6–0.75 typical. Higher preserves source timbre better and weakens the target. |
| `f0_up_key` | -12 to +12 | Pitch shift in semitones. Match the target's range. |
| `filter_radius` | 0–6 | Anti-artifact smoothing. 3 is standard. Higher removes more artifact and more detail. |
| `pitch` | 0–255 | Algorithm quality. 0 is best, slowest. |
| `f0_method` | — | `rmvpe` is most accurate; `harvest` is faster; `dio`/`crepe` are intermediate. |
| `inp_pad` | 0–1 | Padding around the audio. 0.3–0.5 avoids edge artifacts. |
| `rms_mix` | 0–1 | How much the target's loudness is applied. 0.25–0.5. |
| `use_f0_filter` | on/off | Smooths pitch jitter from the source. |

### Choosing index_rate

| Situation | index_rate |
|---|---|
| Source already close to target | 0.4–0.5 |
| Different genders | 0.6–0.7 |
| Very different voice | 0.7–0.8 |
| Maximum target identity | 0.3–0.4 |

### Choosing f0_up_key

Measure the source and target pitch ranges, then shift so they overlap:

```python
import numpy as np
import librosa

f0_src = librosa.yin(audio_src, fmin=50, fmax=1100)
f0_tgt = librosa.yin(audio_tgt, fmin=50, fmax=1100)
print("source median:", np.median(f0_src), "target median:", np.median(f0_tgt))
semitones = 12 * np.log2(np.median(f0_tgt) / np.median(f0_src))
print("shift:", round(semitones))
```

## Voice training checklist

- 5–20 minutes of clean speech for a good model
- 30+ minutes for a high-fidelity model
- No music, no background noise, no overlapping speech
- Consistent room, consistent microphone distance
- Include emotional range — flat audio produces a flat model
