---
name: audio-separation
description: Split audio into stems — vocals, drums, bass, other — with local open-source tools like Demucs and Spleeter, for remixing, sample extraction, karaoke tracks, and preparing audio for further processing. Use when the user wants to isolate vocals, extract instruments, make a karaoke version, or separate audio stems.
metadata:
  promptSignals:
    phrases:
      - separate vocals
      - split audio stems
      - demucs
      - spleeter
      - karaoke track
      - extract instruments
      - remove vocals from song
      - isolate drums
---

# Audio Separation

Splitting a mixed audio file into stems. The core method is a **source
separator** — a neural network trained to recognise and mask each source type.

## Tool comparison

| Tool | Repo | Stems | Licence | Notes |
|---|---|---|---|---|
| **Demucs** | `facebookresearch/demucs` | 4 (vocals, drums, bass, other) or 6 (adds piano, guitar) | MIT | Best general quality |
| **Spleeter** | `deezer/spleeter` | 2, 4, or 5 | MIT | Fast, well-known, older models |
| **audio-separator** | `nomadkaraoke/python-audio-separator` | many | MIT | Wraps Demucs, MDX-Net, VR-Arch; easiest UI |

**Demucs is the default.** `python-audio-separator` is the easiest way to try
multiple models without wiring up each one.

## Demucs

```bash
pip install demucs
```

```bash
# 4 stems (vocals / drums / bass / other)
demucs --two-stems=vocals input.mp3

# 6 stems (adds piano and guitar)
demucs -n htdemucs_6s input.mp3

# specific model
demucs -n mdx_extra_q input.mp3

# GPU
demucs --device cuda -n htdemucs input.mp3
```

Output lands in `separated/htdemucs/<name>/`:

```
vocals.wav  drums.wav  bass.wav  other.wav
```

### Models

| Model | Stems | Speed | Quality |
|---|---|---|---|
| `htdemucs` | 4 | Medium | Good default |
| `htdemucs_ft` | 4 | Slower | **Better** — fine-tuned, use this |
| `htdemucs_6s` | 6 | Medium | Adds piano + guitar |
| `mdx_extra` | 4 | Medium | Slightly better vocals |
| `mdx_extra_q` | 4 | Fast | Quantised, near-`ft` quality |
| `mdx_extra_q_16` | 4 | Fastest | |

`htdemucs_ft` costs a few extra minutes and is noticeably cleaner on vocals.

### Python API

```python
import torch
from demucs.pretrained import get_model
from demucs.apply import apply_model
from demucs.audio import AudioFile, save_audio

model = get_model("htdemucs_ft")
model.cpu()
model.eval()

wav, sr = AudioFile("song.wav").read(
    channels=2, samplerate=44100, mono=False)
ref = wav.mean(0)
wav = (wav - ref.mean()) / (ref.std() + 1e-8)

with torch.no_grad():
    sources = apply_model(model, wav[None], device="cpu", progress=True)[0]
    sources = sources * ref.std() + ref.mean()

save_audio(sources, "stems", samplerate=sr)
```

## python-audio-separator — easiest multi-model runner

```bash
pip install "audio-separator[gpu]"
```

```bash
# pick the best model for the file
audio-separator song.mp3 --model_filename UVR-MDX-NET-Inst_HQ_3.onnx \
  --output_dir separated

# list available models
audio-separator --list_models
```

This wraps MDX-Net, VR-Arch, and Demucs models — the UVR (Ultimate Vocal
Remover) community models are consistently the best for vocals.

## Spleeter

```bash
pip install spleeter
```

```bash
# 2 stems
spleeter separate -i input.mp3 -o output/

# 4 stems (vocals / drums / bass / other)
spleeter separate -p 4 -i input.mp3 -o output/
```

Faster and lighter than Demucs, but vocals leak more.

## Karaoke track

```bash
demucs --two-stems=vocals song.mp3
```

With `--two-stems=vocals`, Demucs writes two files: `vocals.wav` and
`no_vocals.wav`. The latter is the karaoke track — no mixing needed.

To build a karaoke track from the full 4-stem separation instead, sum the
accompaniment stems:

```bash
ffmpeg -i "separated/htdemucs/song/drums.wav" \
  -i "separated/htdemucs/song/bass.wav" \
  -i "separated/htdemucs/song/other.wav" \
  -filter_complex "[0:a][1:a][2:a]amix=inputs=3:duration=longest:normalize=0" \
  -c:a pcm_s16le karaoke.wav
```

## Vocal isolation (karaoke-quality)

The separation is imperfect — you get residual vocal artefacts. For a cleaner
result, use a **vocal isolation** model rather than a stem separator:

```bash
# UVR's MDX-Net vocal isolation model
audio-separator song.mp3 \
  --model_filename UVR-MDX-NET-Voc_FT.onnx \
  --output_dir isolated \
  --output_format WAV
```

This is what karaoke apps use. It is a single model doing one job, so it beats
multistem separation for this specific task.

## Sample extraction

```python
from pydub import AudioSegment

vocals = AudioSegment.from_file("separated/htdemucs/song/vocals.wav")
# take 4 seconds starting at 30s
vocals[30000:34000].export("sample.wav")
```

For **percussive** or **tonal** separation specifically, HPSS is better than a
neural separator and runs instantly:

```python
import librosa

y, sr = librosa.load("song.wav", sr=44100, mono=True)
harmonic, percussive = librosa.decompose.hpss(y)
librosa.output.write_wav("harmonic.wav", harmonic, sr)
librosa.output.write_wav("percussive.wav", percussive, sr)
```

Use HPSS for tonal/percussive splits, neural separation for source-type splits.

## Quality tips

**Vocals still audible in the instrumental** — use `htdemucs_ft` or a UVR MDX
model. The 4-stem model is a compromise; the instrumental stem is
`drums + bass + other`, so it is not a true instrumental.

**Bleeding between stems** — separation is not perfect. Some bleed is normal.
Repeated passes make it worse, not better.

**Artefacts in quiet passages** — the model has less signal to work with. Lower
the volume of those passages rather than expecting a clean split.

**Different sample rate causes clicks on reassembly** — keep everything at the
source rate. Demucs preserves it automatically.

## Reassembly

```bash
# mix a stem back with new music
ffmpeg -i "separated/htdemucs/song/drums.wav" -i new_beat.wav \
  -filter_complex "[0:a]volume=0.8[d];[1:a]volume=0.5[b];[d][b]amix=inputs=2" \
  remix.wav

# normalise the result
ffmpeg -i remix.wav -af loudnorm=I=-14:TP=-1.5 final.wav
```

## Common failures

**"Cannot apply model"** — the model name is wrong. List them with
`demucs --list` or `audio-separator --list_models`.

**CUDA out of memory** — separate in chunks, or use CPU. Demucs on CPU for a
4-minute track takes several minutes.

**Output is silent** — the input was normalised oddly. Check the input levels
first.

**Stems are out of sync with each other** — they were produced in separate
runs. Separate once and keep them together.

**Separation sounds worse than the original** — the source is low-quality or
heavily compressed. Separation amplifies artefacts.

## Reference tools

Other open-source audio tools worth knowing, each over 1,000
GitHub stars — see `references/audio-reference-tools.md`.

## Related skills

`music-generation` · `local-tts-engines` · `voice-cloning-rvc` ·
`media-transcode-pipeline`
