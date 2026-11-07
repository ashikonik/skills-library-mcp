---
name: voice-cloning-rvc
description: Clone and convert voices locally with open-source tools — GPT-SoVITS for zero-shot cloning, RVC for voice conversion with training, OpenVoice for instant cloning, and So-VITS-SVC for singing conversion — covering model training, reference audio requirements, and where each fits. Use when the user wants to clone a voice, convert speech to sound like someone, train a voice model, or do AI voice covers.
metadata:
  promptSignals:
    phrases:
      - clone a voice
      - voice conversion
      - rvc model
      - gpt sovits
      - train a voice model
      - openvoice cloning
      - ai voice cover
      - so-vits-svc
      - make my voice sound like
      - voice identity
---

# Voice Cloning and Conversion

Two different things, often confused:

- **Cloning** — generate speech in a target voice from text.
- **Conversion** — take existing speech and re-voice it.

Conversion preserves the original performance (timing, emotion, inflection).
Cloning produces new speech from a script. Most "AI voice" requests are
conversion; most "AI narrator" requests are cloning.

## Tool comparison

| Tool | Repo | Task | Training data | Quality |
|---|---|---|---|---|
| **GPT-SoVITS** | `RVC-Boss/GPT-SoVITS` | Clone + convert | 1 min (zero-shot) or 5 min (fine-tune) | Best overall |
| **RVC** | `RVC-Project/Retrieval-based-Voice-Conversion-WebUI` | Convert | 10 min | Excellent, large model zoo |
| **OpenVoice** | `myshell-ai/OpenVoice` | Clone (instant) + convert | Instant from 30s | Fast, good tone transfer |
| **So-VITS-SVC** | `svc-develop-team/so-vits-svc` | Convert + singing | 30+ min | Best for singing |
| **Real-Time-Voice-Cloning** | `CorentinJ/Real-Time-Voice-Cloning` | Clone (streaming) | Instant | Low latency, lower quality |

**GPT-SoVITS is the default.** It does both tasks, needs the least data, and
has the most active community.

## GPT-SoVITS

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS

# Linux/macOS: the installer picks device and model source for you
bash install.sh --device CUDA --source HF
# Windows:
pwsh -F install.ps1 --Device CUDA128 --Source HF

# or manually:
pip install -r requirements.txt
pip install -r extra-req.txt --no-deps
```

ffmpeg and `libsox-dev` are required.

The WebUI is the main interface:

```bash
python webui.py                  # unified WebUI
python GPT_SoVITS/inference_webui.py   # inference only
```

### Zero-shot cloning (no training)

The primary interface is `api_v2.py`, an HTTP server:

```bash
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
```

```bash
curl -X POST "http://127.0.0.1:9880/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Your text goes here.",
    "text_lang": "en",
    "ref_audio_path": "reference.wav",
    "prompt_lang": "en",
    "prompt_text": "The exact words said in reference.wav"
  }' \
  --output out.wav
```

Weight selection is done over HTTP before the first generation:

```bash
curl "http://127.0.0.1:9880/set_gpt_weights?weights_path=GPT_SoVITS/pretrained_models/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"
curl "http://127.0.0.1:9880/set_sovits_weights?weights_path=GPT_SoVITS/pretrained_models/s2Gv2ProPlus.pth"
```

`prompt_text` must be the **verbatim transcript of the reference audio**. This
is how GPT-SoVITS captures the voice's cadence, not just timbre.

Useful request fields: `speed_factor` (default 1.0), `top_k`, `top_p`,
`temperature`, `seed`, `text_split_method`, `batch_size`, `streaming_mode`,
`media_type` (`wav` or `mp3`), and `aux_ref_audio_paths` for several
references.

### Fine-tuning (better quality)

You need:
- 1 minute of audio for a quick result
- 5 minutes for a good one
- 30+ minutes for an excellent one

The dataset scripts live in `GPT_SoVITS/prepare_datasets/`:

```bash
# 1. slice and denoise the raw audio
python tools/slice_audio.py --input_path ./raw_audio --output_path ./sliced
python tools/cmd-denoise.py --input_path ./sliced --type vocal

# 2. the three prepare steps
python GPT_SoVITS/prepare_datasets/1-get-text.py \
  --input_dir ./prepared --output_dir ./prepared
python GPT_SoVITS/prepare_datasets/2-get-hubert-wav32k.py \
  --input_dir ./prepared --output_dir ./prepared
python GPT_SoVITS/prepare_datasets/3-get-semantic.py \
  --input_dir ./prepared --output_dir ./prepared

# 3. train the two stages
python GPT_SoVITS/s1_train.py --config configs/s1longer.yaml \
  --input_dir ./prepared --output_dir ./weights
python GPT_SoVITS/s2_train.py --config configs/s2config.yaml \
  --input_dir ./prepared --output_dir ./weights
```

`s2_train_v3.py` and `s2_train_v3_lora.py` train the v3 / LoRA variants
instead.

## RVC — voice conversion

RVC converts existing audio. It has a large community model zoo.

```bash
git clone https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI.git
cd Retrieval-based-Voice-Conversion-WebUI

# CUDA 12.8
python -m pip install torch==2.7.1+cu128 torchaudio==2.7.1+cu128 \
  --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirments_cu128_py312.txt

# or CPU
python -m pip install -r requirments_cpu_py312.txt

python webui.py
```

The pretrained assets download separately into `assets/`:

```bash
python -m pip install --upgrade huggingface_hub
huggingface-cli download RVC-Boss/GPT-SoVITS --include "pretrained/*" "pretrained_v2/*" --local-dir assets
python -m zipfile -e .model-downloads/mute.zip logs
```

### Offline conversion

RVC ships a CLI for headless conversion:

```bash
python -m infer.cli \
  --model "assets/weights/character.pth" \
  --input source.wav \
  --output converted.wav \
  --index-rate 0.75 \
  --pitch 0 \
  --f0-method rmvpe \
  --format wav
```

| Flag | Effect |
|---|---|
| `--index-rate` | **The important one.** 0.6–0.8 for a convincing target voice. Below 0.4 sounds like the original with a filter. |
| `--pitch` | Semitones to shift. Use to match the source and target pitch ranges, or to avoid chipmunk artefacts. |
| `--f0-method` | `rmvpe` (default) or `pm`. `pm` is slower but more accurate on breathy voices. |
| `--protect` | Protects the consonant and transient region from being flattened. Default 0.33. |
| `--rms-mix-rate` | How much of the original RMS envelope is preserved. Default 1.0. |
| `--resample-sr` | Output sample rate. 0 keeps the model's. |
| `--model` | A model filename or a path to a `.pth`. Multi-speaker models need `--speaker-id`. |
| `--index` | An explicit `.index` path. The matching speaker index is chosen automatically when omitted. |
| `--list-speakers` | Print the model's speaker metadata and exit. |

`--input` and `--output` accept directories too, and `--recursive` walks
subdirectories.

### Training an RVC model

Requirements:
- 10+ minutes of clean, single-speaker audio
- 44.1kHz WAV
- No background music, no other speakers, minimal reverb

The training scripts are in `train/`, and they read their configuration from
the WebUI's config rather than from command-line flags:

```bash
# 1. preprocess — positional arguments: input dir, sample rate, n_processes,
#    experiment dir, noparallel, per, manifest path
python train/preprocess.py "dataset/raw" 44100 4 "logs/experiment" True 0.1

# 2. train — settings come from the experiment config in configs/
python train/train.py

# 3. build the index file (improves timbre retention)
python train/train_index.py "logs/experiment" "logs/experiment/added.index"
```

The index file (`.index`) improves timbre retention. Build it after training.

## OpenVoice — instant cloning

```bash
git clone https://github.com/myshell-ai/OpenVoice.git
cd OpenVoice
pip install -e .

# V2 checkpoints (MIT, free for commercial use)
# https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip
#   -> extract to checkpoints_v2/

# V2 also needs MeloTTS for the base speakers
pip install git+https://github.com/myshell-ai/MeloTTS.git
python -m unidic download
```

```python
import torch
from openvoice import se_extractor
from openvoice.api import ToneColorConverter

converter = ToneColorConverter(
    'checkpoints_v2/converter/config.json',
    device='cuda')
converter.load_ckpt('checkpoints_v2/converter/checkpoint.pth')

target_se, audio_name = se_extractor.get_se(
    "reference.wav",
    converter,
    target_dir='processed',
)

source_se = torch.load('checkpoints_v2/base_speakers/ses/en-default.pth')
converter.convert(
    audio_src_path="source.mp3",
    src_se=source_se,
    tgt_se=target_se,
    output_path="converted.wav",
    tau=0.3,
)
```

`get_se(audio_path, vc_model, target_dir='processed', vad=True)` returns the
speaker embedding and a generated name for the cached segment. `vad=True`
splits the reference with voice-activity detection; `vad=False` uses
Whisper-based splitting instead.

`tau` controls how much of the source style survives the conversion — higher
preserves more of the original delivery.

Tone colour conversion only — it transfers timbre, not speaking style. Faster
and lighter than GPT-SoVITS, less expressive. OpenVoice V2 is MIT and
commercially usable.

## Reference audio requirements

This is where most projects fail. The rules:

1. **Clean** — no music, no keyboard, no traffic, no other speakers.
2. **Single speaker** — no overlap, no responses to questions.
3. **5–30 seconds** — under 5 is too short for the model to characterise;
   over 30 is usually compiled from bad segments.
4. **Consistent tone** — pick one emotional register. Excited-to-calm audio
   produces a voice that sounds unstable.
5. **No effects** — no reverb, no pitch shift, no noise reduction artefacts.
6. **Varied content** — not the same word repeated. The model learns prosody
   from real sentences.

Check it before use:

```bash
ffmpeg -i reference.wav -af "silencedetect=n=-40dB:d=0.3" -f null - 2>&1 | grep silence
ffmpeg -i reference.wav -af astats=metadata=1 -f null - 2>&1 | grep RMS
```

## Ethical and legal use

- Only clone voices you have **consent** to clone — the speaker's own, or
  explicitly licensed.
- Disclose synthetic voice in contexts where it could mislead.
- Some jurisdictions have specific rules about synthetic media in
  advertising, elections, and journalism.
- Do not train on third-party voice performances from songs or films.

## Common failures

**Cloned voice sounds like a robot** — insufficient or noisy training data.
Use a cleaner reference.

**Conversion keeps the original voice** — `index_rate` too low, or the model was
trained on audio that already resembles the source.

**Chipmunk / deep voice** — `f0_up_key` is pushing the pitch outside the model's
training range. Use 0 and let the model handle it.

**Model outputs are 44.1kHz and the pipeline wants 16kHz** — resample
explicitly: `ffmpeg -i out.wav -ar 16000 -ac 1 out16k.wav`.

**Training diverges or outputs garbage** — the dataset has inconsistent
loudness. Normalise first: `ffmpeg -i in.wav -af loudnorm=I=-20 out.wav`.

**Licence issue** — RVC and GPT-SoVITS themselves are permissive, but the
**voice** is not yours to clone. Check the source audio's licence too.

## Reference tools

Other open-source audio tools worth knowing, each over 1,000
GitHub stars — see `references/audio-reference-tools.md`.

## Related skills

`local-tts-engines` · `lip-sync` · `music-generation` · `tts-to-video` ·
`audio-separation`
