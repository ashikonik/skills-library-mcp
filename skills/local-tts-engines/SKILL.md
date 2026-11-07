---
name: local-tts-engines
description: Generate speech locally with open-source TTS engines — Piper, Coqui XTTS, Kokoro, Bark, VoxCPM, CosyVoice, Qwen3-TTS, Dia, ChatTTS, and Supertonic — with model comparison, installation, voice cloning support, emotion control, and API usage. Use when the user wants to generate a voiceover, synthesize speech, do text-to-speech locally, or needs a free offline TTS engine.
metadata:
  promptSignals:
    phrases:
      - text to speech
      - generate voiceover
      - tts engine
      - piper tts
      - coqui xtts
      - kokoro tts
      - bark tts
      - local speech synthesis
      - offline voice generation
      - elevenlabs alternative
      - voiceover audio
---

# Local Text-to-Speech

Open TTS engines that run offline. Most produce speech good enough for
voiceover; the differences are in voice quality, cloning support, and control.

## Engine comparison

| Engine | Repo | Licence | Cloning | Emotion | Speed | VRAM |
|---|---|---|---|---|---|---|
| **Piper** | `OHF-Voice/piper1-gpl` | GPL-3.0 | No | No | Very fast (RTF <0.1) | None (CPU) |
| **Kokoro** | `hexgrad/kokoro` | Apache-2.0 | No | No | Fast | <1GB |
| **Coqui XTTS v2** | `coqui-ai/TTS` | MPL-2.0 | ✅ 6s sample | Some | Moderate | 2GB |
| **VoxCPM** | `OpenBMB/VoxCPM` | Apache-2.0 | ✅ | ✅ | Moderate | 4GB |
| **CosyVoice** | `QwenAudio/CosyVoice` | Apache-2.0 | ✅ | ✅ | Moderate | 4GB |
| **Qwen3-TTS** | `QwenLM/Qwen3-TTS` | Apache-2.0 | ✅ | ✅ | Moderate | 4GB |
| **Dia** | `nari-labs/dia` | Apache-2.0 | No | ✅✅ | Fast | 2GB |
| **Bark** | `suno-ai/bark` | MIT | Yes (loose) | ✅ | Slow | 4GB |
| **ChatTTS** | `2noise/ChatTTS` | AGPL-3.0 | No | ✅ | Fast | 2GB |
| **Supertonic** | `supertone-oss-archive/supertonic` (archived) | MIT | No | No | Very fast | <1GB |

**Recommendations:**
- **Bulk narration, no cloning** → Piper (fastest, tiny) or Kokoro (better quality)
- **Clone a specific voice** → XTTS v2 or CosyVoice
- **Expressive dialogue with tags** → Dia
- **Multilingual** → CosyVoice or Qwen3-TTS (strong Chinese and English)
- **No GPU at all** → Piper or Kokoro, both CPU-only

**Two engines in this table are archived** — Piper's old `rhasspy/piper` repo
and all of Supertonic. Use the current repos listed above, not the old ones.

## Piper — fastest, CPU-only

Piper lives at `OHF-Voice/piper1-gpl` (GPL-3.0). The older `rhasspy/piper`
repo is archived — it was MIT, but the project has since moved and the
licence is now GPL-3.0. This skill documents Piper's interface; it does not
vendor Piper's code, so Piper's licence applies to Piper itself.

```bash
pip install piper-tts

# list the available voices
python3 -m piper.download_voices

# download one into the current directory
python3 -m piper.download_voices en_US-lessac-medium
```

```bash
# synthesise to a file
python3 -m piper -m en_US-lessac-medium -f out.wav -- 'Your text here.'

# read the text from stdin instead
echo "Your text here." | python3 -m piper -m en_US-lessac-medium -f out.wav

# play straight to the speakers (omit -f)
python3 -m piper -m en_US-lessac-medium -- 'This will play on your speakers.'

# a specific voice, from a voice directory
python3 -m piper --data-dir ./voices -m en_US-amy-medium -f out.wav -- 'Your text here.'
```

The CLI takes text as a trailing argument after `--`, or on stdin. `-m` selects
the voice, `-f` writes a WAV file, `--data-dir` points at a directory of
downloaded voices. Other useful flags: `--cuda` (needs `onnxruntime-gpu`),
`--input-file`, `--sentence-silence`, `--volume`, `--no-normalize`.

Each run reloads the voice model, so it is slow for one-off lines. For
batch work run the web server instead, or use the Python API.

## Kokoro — best quality for a small model

```bash
pip install kokoro
```

```python
from kokoro import KPipeline

pipeline = KPipeline(lang_code="a")   # "a" = American English, "b" = British

for i, (gs, ps, audio) in enumerate(
        pipeline("Your text here", voice="af_heart")):
    import soundfile as sf
    sf.write(f"out_{i}.wav", audio, 24000)
```

`voice` names: `af_heart`, `af_bella`, `am_michael`, `bf_emma`, `bm_george`.

**Kokoro is the strongest default** for English voiceover — clean, natural, and
runs on CPU in real time.

## Coqui XTTS v2 — cloning from 6 seconds

```bash
pip install TTS
```

```python
from TTS import TTS
import torch

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)

tts.tts_to_file(
    text="Your text here.",
    speaker_wav="reference.wav",          # 6+ seconds of clean speech
    language="en",
    file_path="out.wav",
)
```

```python
# generate for multiple speakers at once
tts.tts_to_file(text="Line one.", speaker_wav="a.wav", language="en",
                file_path="a_out.wav", split_sentences=True)
```

**Reference audio quality matters more than reference length.** 6–30 seconds of
clean, single-speaker audio with no music and no reverb. A 6-second clip of a
noisy recording clones the noise too.

## CosyVoice — cloning plus emotion

```bash
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice
conda create -n cosyvoice -y python=3.10
conda activate cosyvoice
pip install -r requirements.txt
```

Download a checkpoint first — the code calls `snapshot_download` for you if
the directory is missing, but doing it explicitly is clearer:

```python
from huggingface_hub import snapshot_download
snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512',
                  local_dir='pretrained_models/Fun-CosyVoice3-0.5B')
```

The canonical id is `FunAudioLLM/Fun-CosyVoice3-0.5B-2512`; the unsuffixed
`Fun-CosyVoice3-0.5B` redirects to it. There is also an `_RL` checkpoint
(`Fun-CosyVoice3-0.5B-2512_RL`) with better prosody and lower latency.

```python
from cosyvoice.cli.cosyvoice import CosyVoice3

m = CosyVoice3("pretrained_models/Fun-CosyVoice3-0.5B", load_trt=True)

for j in m.inference_zero_shot(
        "Your text here.",
        prompt_text="The reference transcript.",
        prompt_wav="zero_shot_prompt.wav"):
    print(j['tts_speech'])
```

The model family shares one API, with a class per generation:

| Class | Use |
|---|---|
| `CosyVoice` | The 300M base / SFT / Instruct models |
| `CosyVoice2` | `CosyVoice2-0.5B` |
| `CosyVoice3` | `Fun-CosyVoice3-0.5B-2512` — the current default |

**Use `AutoModel(model_dir=...)` instead of picking a class** — it reads the
checkpoint's `cosyvoice.yaml` / `cosyvoice2.yaml` / `cosyvoice3.yaml` and
returns the right one.

The inference methods:

| Method | What it does |
|---|---|
| `inference_zero_shot(tts_text, prompt_text, prompt_wav)` | Clone a voice from a reference clip |
| `inference_cross_lingual(tts_text, prompt_wav)` | Clone the voice, speak a *different* language |
| `inference_instruct(tts_text, spk_id, instruct_text)` | Speak with an emotion instruction |
| `inference_instruct2(tts_text, instruct_text, prompt_wav)` | Emotion + cloned voice (v2/v3) |
| `inference_sft(tts_text, spk_id)` | Use a built-in speaker |
| `inference_vc(source_wav, prompt_wav)` | Voice conversion — keep the words, swap the voice |

The GitHub repo is now `QwenAudio/CosyVoice`; the README's clone URL still
points at `FunAudioLLM/CosyVoice`, which redirects there. The Hugging Face
model ids stay under the `FunAudioLLM/` org.

## VoxCPM — voice design without reference audio

```bash
pip install voxcpm
```

```python
import soundfile as sf
from voxcpm import VoxCPM

model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)

wav = model.generate(
    text="VoxCPM2 is the current recommended release for realistic speech.",
    cfg_value=2.0,
    inference_timesteps=10,
    seed=42,
)
sf.write("out.wav", wav, model.tts_model.sample_rate)
```

VoxCPM is **tokenizer-free** — it generates continuous speech representations
directly, which is why it can be steered three different ways:

**Voice design** — no reference audio needed. Put the description in
parentheses at the start of the text:

```python
wav = model.generate(
    text="(A young woman, gentle and sweet voice)Hello, welcome to VoxCPM2!",
    cfg_value=2.0, inference_timesteps=10, seed=42,
)
```

**Controllable cloning** — clone the timbre from a reference and still steer
speed, emotion, and style with a leading instruction:

```python
wav = model.generate(
    text="(slightly faster, cheerful tone)This is a cloned voice.",
    reference_wav_path="voice.wav",
    cfg_value=2.0, inference_timesteps=10, seed=42,
)
```

**Ultimate cloning** — pass the reference audio *and* its exact transcript
for the highest similarity. Use the same clip for both parameters:

```python
wav = model.generate(
    text="This is an ultimate cloning demonstration.",
    prompt_wav_path="voice.wav",
    prompt_text="The transcript of the reference audio.",
    reference_wav_path="voice.wav",
)
```

## Qwen3-TTS — multilingual with strong Chinese

```bash
pip install -U qwen-tts
```

```python
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    device_map="cuda:0",
    dtype=torch.bfloat16,
    attn_implementation="flash_attention_2",
)

wavs, sr = model.generate_custom_voice(
    text="Your text here.",
    language="English",     # or "Auto" to let the model pick
    speaker="Aiden",
    # instruct="Very happy.",   # optional emotion control
)
sf.write("out.wav", wavs[0], sr)
```

`generate_custom_voice` takes a string or a list, so batching is just
passing lists for `text`, `language`, and `speaker`.

Built-in speakers include `Vivian`, `Serena`, `Uncle_Fu`, `Dylan`, `Eric`
(Chinese), `Ryan`, `Aiden` (English), `Ono_Anna` (Japanese), and `Sohee`
(Korean). Use each speaker's native language for the best quality. Call
`model.get_supported_speakers()` and `model.get_supported_languages()` to
see what the loaded checkpoint actually offers.

For cloning, the base model uses `generate_voice_clone`:

```python
wavs, sr = model.generate_voice_clone(
    text="Your text here.",
    ref_audio="reference.wav",
    ref_text="The reference transcript.",
)
```

To reuse a voice across many lines, synthesise a reference clip with the
VoiceDesign model, build a reusable prompt with `create_voice_clone_prompt`,
then pass that prompt to `generate_voice_clone`.

## Dia — dialogue with audio tags

```bash
pip install -e git+https://github.com/nari-labs/dia.git
# the transformers path needs main-branch transformers:
pip install git+https://github.com/huggingface/transformers.git
```

```python
from transformers import AutoProcessor, DiaForConditionalGeneration

model_checkpoint = "nari-labs/Dia-1.6B-0626"

text = [
    "[S1] You get full control over scripts and voices. "
    "[S2] Try it now on GitHub or Hugging Face. [S1] Wow. Amazing. (laughs)"
]

processor = AutoProcessor.from_pretrained(model_checkpoint)
inputs = processor(text=text, padding=True, return_tensors="pt").to("cuda")

model = DiaForConditionalGeneration.from_pretrained(model_checkpoint).to("cuda")
outputs = model.generate(
    **inputs,
    max_new_tokens=3072,
    guidance_scale=3.0,
    temperature=1.8,
    top_p=0.90,
    top_k=45,
)

processor.batch_decode(outputs)
processor.save_audio(outputs, "out.mp3")
```

The repo also ships its own `dia.model.Dia` class, which works without the
transformers integration:

```python
import soundfile as sf
from dia.model import Dia

model = Dia.from_pretrained("nari-labs/Dia-1.6B")
audio = model.generate(
    "[laughs] Oh, that's terrible. [sighs] I really thought it would work."
)
sf.write("out.wav", audio, 44100)
```

Dia understands non-verbal tags: `(laughs)`, `(sighs)`, `(clears throat)`,
`(gasps)`, `(coughs)`. Speaker turns are marked `[S1]`, `[S2]`. This is what
makes it good for dialogue and bad for straight narration — the tags make it
wander.

## Bark — the original expressive one

```bash
# Do NOT use `pip install bark` — that installs a different, squatted package
# that is not managed by Suno.
pip install git+https://github.com/suno-ai/bark.git
```

```python
import numpy as np
import soundfile as sf
from bark import SAMPLE_RATE, generate_audio, preload_models

preload_models()

audio = generate_audio(
    "Your text here. (laughs)",
    history_prompt="v2/en_speaker_6",   # preset name or a saved prompt dict
    text_temp=0.7,
    waveform_temp=0.7,
)
sf.write("out.wav", audio, SAMPLE_RATE)
```

`history_prompt` takes a preset name (`"v2/en_speaker_6"`) or a full prompt
dict saved from a previous generation (`output_full=True`). `text_temp` and
`waveform_temp` control variation — 1.0 is more diverse, 0.0 more
conservative.

Bark hallucinates background noise and breathing — charming for character work,
unusable for clean voiceover. It also drifts on long text: it works well
around 13 seconds of speech, and the repo has a long-form notebook for
more.

Bark also ships a CLI:

```bash
python -m bark --text "Your text here." --voice_preset "v2/en_speaker_6" --out out.wav
```

## Supertonic — very fast, CPU-only ONNX (archived)

> **Supertonic is archived.** The project is preserved under the
> `supertone-oss-archive` GitHub org and the `supertone-oss-archive` Hugging
> Face namespace. No further development, fixes, or security patches. The code
> still works and the weights are downloadable — but do not start a new
> project on it. Kokoro or Piper are better maintained CPU-only choices.

```bash
git clone https://github.com/supertone-oss-archive/supertonic.git
cd supertonic
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install huggingface_hub

# download the ONNX model, config, and preset voice styles
hf download supertone-oss-archive/supertonic-3 \
  --revision aafc6e32416a594460b32413efc49d7fe4ce6d46 \
  --local-dir assets
```

```bash
python -m pip install -r py/requirements.txt
cd py
python example_onnx.py --n-test 1 --text "Your text here." --lang en
# output lands in py/results/
```

`--lang` selects the voice's language — Supertonic 3 covers 31 languages. The
`--revision` pin matters: it locks the archived snapshot so the download
cannot drift.

A `supertonic` PyPI package exists, but older releases look for models under
the old `Supertone` HF namespace. If you use it, download `assets/` as above
and pass `model_dir` with `auto_download=False`.

## Voice selection criteria

For narration, pick on: **clarity at 16kHz**, **no reverb**, **consistent pace**,
and **no unusual accent**. For character work, pick on expressiveness.

Test by generating the **same 30-second script** in 3–4 voices and listening at
1× on phone speakers, not headphones. That is where most voiceover is heard.

## Post-processing

```bash
# normalise loudness to -14 LUFS (social) or -16 (broadcast)
ffmpeg -i raw.wav -af loudnorm=I=-14:TP=-1.5:LRA=11 out.wav

# trim silence at start and end
ffmpeg -i out.wav -af silenceremove=start_periods=1:start_silence=0.05 \
  -af areverse,silenceremove=start_periods=1:start_silence=0.05,areverse out_trim.wav

# high-pass to remove rumble
ffmpeg -i out.wav -af "highpass=f=80" out_clean.wav
```

Trim silence **before** loudness normalisation, not after.

## Common failures

**Cloned voice sounds wrong** — the reference audio is poor. Re-record in a
quiet room, 10+ seconds, single speaker, no music.

**Output is choppy or slow** — sample rate mismatch when concatenating. Force
everything to the same rate: `ffmpeg -i in.wav -ar 24000 -ac 1 out.wav`.

**Different engines produce different loudness** — normalise each to the same
LUFS target before assembly.

**Kokoro/Piper pronunciation is wrong** — they do not support phoneme overrides
well. Add spacing or use a different engine for that phrase.

**Bark adds background chatter** — that is the model. Use Kokoro or Piper for
clean narration.

**Long text drifts** — generate in sentence-sized chunks and concatenate, rather
than passing a whole page.

## Reference tools

Other open-source audio tools worth knowing, each over 1,000
GitHub stars — see `references/audio-reference-tools.md`.

## Related skills

`voice-cloning-rvc` · `lip-sync` · `subtitle-generation` · `tts-to-video` ·
`music-generation` · `audio-separation` · `shorts-reels-pipeline`
