---
name: music-generation
description: Generate music, sound effects, and ambient audio locally with open-source models — AudioCraft MusicGen and AudioGen, ACE-Step, YuE, Stable Audio Open, and Bark's audio modes — with model comparison, prompting, duration limits, and looping and mixing techniques for video. Use when the user wants background music, a soundtrack, a jingle, sound effects, or AI-generated music for a video.
metadata:
  promptSignals:
    phrases:
      - generate music
      - ai music
      - background music for video
      - musicgen
      - audiocraft
      - sound effects
      - jingle
      - ace step
      - generate a soundtrack
      - ambient music
---

# Music and Sound Generation

Generating music and sound locally for video. The models are good enough for
background beds and sound effects; they are not good at producing a song with
a structure you can rely on.

## Model comparison

| Model | Repo | Licence | Duration | Strengths |
|---|---|---|---|---|
| **MusicGen** | `facebookresearch/audiocraft` | MIT (code), CC-BY-NC for weights | 30s | Instrumental beds, very good timbre |
| **AudioGen** | `facebookresearch/audiocraft` | Same | 10s | Sound effects, environmental audio |
| **ACE-Step 1.5** | `ace-step/ACE-Step-1.5` | MIT | 10 min | Full songs with structure, fastest |
| **YuE** | `multimodal-art-projection/YuE` | Apache-2.0 | 5 min | Lyrics-to-song, symbolic planning |
| **Stable Audio Open** | `Stability-AI/stable-audio-tools` | MIT (code), weights non-commercial | 47s | High fidelity, cinematic |
| **ACE-Step vocals** | `ace-step/ACE-Step-1.5` | MIT | — | Vocals on top of MusicGen |

**ACE-Step for anything song-shaped. MusicGen for instrumental beds and loops.**

## MusicGen

```bash
pip install audiocraft
```

```python
import torch
from audiocraft.models import MusicGen

model = MusicGen.get_pretrained("facebook/musicgen-small")
model.set_generation_params(duration=30)   # max 30s for small/medium

prompt = "warm lo-fi hip hop beat, dusty drums, mellow electric piano, 90 bpm"
out = model.generate([prompt], progress=True)   # [batch, channels, samples]
torchaudio.save("out.wav", out[0], 32000)
```

Model sizes:

| Model | Params | VRAM | Quality |
|---|---|---|---|
| `facebook/musicgen-small` | 300M | 2GB | Good for drafts |
| `facebook/musicgen-medium` | 1.5B | 6GB | The sweet spot |
| `facebook/musicgen-large` | 3.3B | 12GB | Best |
| `facebook/musicgen-stereo-medium` | 1.5B | 6GB | Stereo |
| `facebook/musicgen-melody` | 1.5B | 6GB | Also accepts a melody as input |

```python
model = MusicGen.get_pretrained("facebook/musicgen-medium")
model.set_generation_params(
    duration=30,
    guidance_scale=3.0,       # prompt adherence; > 3 gets harsh
    temperature=1.0,          # variation between runs
    top_k=250,                # lower = more predictable
    top_p=0.0,
)
```

**Generate stereo by generating twice and widening**, or use the 3.5B model.

## AudioGen (sound effects)

```python
from audiocraft.models import AudioGen

model = AudioGen.get_pretrained("facebook/audiogen-medium")
model.set_generation_params(duration=10)

out = model.generate([
    "dog barking, medium distance, outdoor",
    "heavy door slamming shut",
    "rain on a metal roof, steady",
])
torchaudio.save("sfx.wav", out[0], 16000)
```

AudioGen is excellent for sound design. 10 seconds max, so loop for longer beds.

## ACE-Step — full songs with structure

```bash
git clone https://github.com/ace-step/ACE-Step-1.5.git
cd ACE-Step-1.5
uv sync          # Python 3.11-3.12

uv run acestep             # Gradio UI on http://localhost:7860
uv run acestep-api         # REST API on http://localhost:8001
```

The CLI is **wizard/config driven** — it takes a `.toml` config, not a long
list of flags:

```bash
python cli.py                          # interactive wizard
python cli.py --config config.toml     # generate from a saved config
python cli.py --configure              # build a config without generating
```

The wizard covers task selection, DiT and LM model choice, caption, lyrics
mode (instrumental / auto-generate / file / paste), output count, and advanced
parameters. It saves everything to a `.toml` whose keys map directly onto the
runtime settings — `caption`, `prompt`, `lyrics`, `duration`, `bpm`,
`keyscale`, `timesignature`, `instrumental`, `seed`, `guidance_scale`,
`inference_steps`, `save_dir`, and others.

```toml
# config.toml — the shape the wizard writes
caption = "upbeat electronic pop, catchy chorus"
lyrics = """
[verse]
Walking through the city lights
[chorus]
We are the ones who never sleep
"""
duration = 60
bpm = 120
instrumental = false
save_dir = "output"
```

```bash
python cli.py --config config.toml
```

To prompt the LM directly, put the instruction in `instruction.txt` in the
project root — when `thinking=True` and a config is loaded, that file is used
as the pre-loaded prompt instead of pausing for interactive editing.

ACE-Step produces a song with verse/chorus structure in one pass, from 10
seconds to 10 minutes. This is the right tool when you need music that matches
a video's arc rather than a generic loop.

**VRAM** drives the model choice: 2B turbo runs in under 6GB, the XL (4B DiT)
variants want 12GB with offload and 20GB+ without it. The `acestep` launcher
auto-detects the tier and picks a config for you.

## Stable Audio Open

The upstream project is **`Stability-AI/stable-audio-tools`** (MIT code). There
is no `stable-audio-open` repo — the weights live on Hugging Face as
`stabilityai/stable-audio-open-1.0`, and you must accept the model terms there
before the first download.

The easiest route is the bundled Gradio UI:

```bash
git clone https://github.com/Stability-AI/stable-audio-tools.git
cd stable-audio-tools
uv sync                                  # or: pip install "stable-audio-tools[train]"
uv run python run_gradio.py --pretrained-name stabilityai/stable-audio-open-1.0
```

For scripted generation, use the low-level API. `stable_audio_tools` exports
`get_pretrained_model` and `create_model_from_config` — there is **no**
`create_diffusion_pipeline`; the generator is `generate_diffusion_cond`:

```python
import torch, torchaudio
from stable_audio_tools import get_pretrained_model
from stable_audio_tools.inference.generation import generate_diffusion_cond

model, config = get_pretrained_model("stabilityai/stable-audio-open-1.0")
model = model.to("cuda").half()

sample_rate = config["sample_rate"]          # 44100 for stable-audio-open-1.0
seconds = 30
conditioning = {
    "prompt": "ambient cinematic drone, slow build",
    "seconds_start": 0.0,
    "seconds_total": float(seconds),
}

audio = generate_diffusion_cond(
    model,
    steps=250,
    cfg_scale=6,
    conditioning=[conditioning],
    negative_conditioning=[{**conditioning, "prompt": "drums, vocals, distortion"}],
    batch_size=1,
    sample_size=sample_rate * seconds,
    sample_rate=sample_rate,
    seed=-1,
    device="cuda",
)

torchaudio.save("out.wav", audio[0].cpu(), sample_rate)
```

Key details:

- `conditioning` is a **list of dicts**, one per batch item, each with
  `prompt`, `seconds_start`, and `seconds_total`.
- `sample_size` is in **samples**, not seconds — multiply by the sample rate.
- `seed=-1` picks a random seed; set an integer for reproducible output.
- `cfg_scale` defaults to 6. Raise it for stronger prompt adherence.
- `adapt_duration_to_conditioning=True` shortens the generation window to
  `seconds_total` instead of rendering the full `sample_size`.

**Licence:** the *code* is MIT, but the *weights* are under Stability AI's
non-commercial community licence. Check before using in monetised content.
`stabilityai/stable-audio-open-small` is a lighter checkpoint (1.2B) for
faster iteration.

## Prompting for music

Describe **genre, instrumentation, tempo, mood, and production quality**:

```
"cinematic orchestral trailer music, cello and piano, building tension,
120 bpm, dramatic, wide reverb"
```

```
"lo-fi hip hop, dusty vinyl texture, mellow keys, soft drums, 80 bpm, warm"
```

Avoid: artist names (the models will not reliably reproduce them, and it is
unclear how they were handled), specific song titles, or "radio edit" style
instructions.

## Getting a usable length

MusicGen caps at 30 seconds. To build a longer bed, **generate several 30s
segments with a consistent prompt suffix and crossfade them.**

```python
import numpy as np, soundfile as sf, torch
from audiocraft.models import MusicGen

model = MusicGen.get_pretrained("facebook/musicgen-medium")
model.set_generation_params(duration=30)

PROMPT = "ambient pad, warm analog synth, slow evolution, no drums, 90 bpm"
segments = []
for i in range(8):
    out = model.generate([PROMPT + f", variation {i}"])[0]
    segments.append(out)

def crossfade(a, b, n):
    fade = torch.linspace(1, 0, n)
    return torch.cat([a[:-n], a[-n:] * fade + b[:n] * (1 - fade)])

result = segments[0]
for seg in segments[1:]:
    result = crossfade(result, seg, int(model.sampler.sample_rate * 2.0))

sf.write("bed.wav", result.numpy(), model.sampler.sample_rate)
```

Two seconds of crossfade is enough for ambient material. Use 4 seconds for
percussive material or the transitions will sound clipped.

## Audio processing for video

```bash
# loop a 30s bed to 3 minutes
ffmpeg -stream_loop -1 -i bed.wav -t 180 -af "afade=t=in:st=0:d=2,afade=t=out:st=178:d=2" long_bed.wav

# duck music under voiceover (sidechain-style)
ffmpeg -i music.wav -i voice.wav -filter_complex \
  "[0:a][1:a]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[ducked];\
[1:a][ducked]amix=inputs=2:duration=first:weights=1 1" \
  mixed.wav

# loudness: music at -22 LUFS under voice at -16 LUFS
ffmpeg -i music.wav -af "loudnorm=I=-22:TP=-3:LRA=11" music_norm.wav
```

**Mix levels for video:**
- Narration: −16 LUFS
- Music bed under narration: −22 to −26 LUFS
- Music alone: −14 LUFS
- True peak: −1.5 dBTP

## Sound design layering

A convincing soundscape is layers, not one file:

```
room tone (quiet, looped)      -20 dB
distant ambience (wind, traffic) -18 dB
specific foley (footsteps, door)  -12 dB
music bed                        -22 dB
narration                        -16 dB
```

Generate each with AudioGen and mix.

## Common failures

**Music has a click or pop at the loop point** — no crossfade. Use the
crossfade code above.

**Generation stops at 30 seconds** — MusicGen's limit. Use ACE-Step for long
pieces, or loop and crossfade.

**Output sounds noisy or harsh** — `guidance_scale` too high. Drop to 2.0–2.5.

**Vocals are unintelligible gibberish** — MusicGen does not do intelligible
vocals. Use ACE-Step or YuE if you need words.

**Everything sounds the same** — `temperature` too low. Raise it, or vary the
prompt meaningfully between generations.

**Music clips when mixed with voice** — the levels are wrong. Normalise each
source separately before mixing.

**Licence restricts commercial use** — Stable Audio Open weights are
non-commercial. MusicGen weights are CC-BY-NC. ACE-Step is MIT. Check before
publishing monetised content.

## Reference tools

Other open-source audio tools worth knowing, each over 1,000
GitHub stars — see `references/audio-reference-tools.md`.

## Related skills

`audio-separation` · `local-tts-engines` · `stock-media-sourcing` ·
`shorts-reels-pipeline` · `media-transcode-pipeline`
