# TTS engine comparison

| Engine | VRAM | Languages | Cloning | Speed | Quality |
|---|---|---|---|---|---|
| Piper | CPU | 40+ | No | Very fast | Good |
| Kokoro | 1 GB | 8 | No | Real-time | Excellent |
| XTTS-v2 | 4 GB | 17 | Yes | Real-time | Very good |
| ChatTTS | 4 GB | zh/en | No | Real-time | Good, expressive |
| CosyVoice | 6 GB | zh/en | Yes | Fast | Excellent |
| Qwen3-TTS | 8 GB | 10+ | Yes | Fast | Very good |
| Dia | 4 GB | en | No | Slow | Excellent, chatty |
| Bark | 4 GB | 10+ | Yes | Slow | Good, dramatic |
| Supertonic | CPU (~99M params) | 31 (v3) | No (fixed voices) | Real-time | Very good |

> **Supertonic and Piper's old repo are archived.** Supertonic 3 is a 99M-
> parameter ONNX model that runs on CPU with no GPU, has expression tags
> (`<laugh>`, `<breath>`, `<sigh>`), and ships **fixed voices only** — there is
> no official voice-cloning pipeline.

## Piper — the workhorse

```bash
pip install piper-tts
python3 -m piper.download_voices en_US-lessac-medium
python3 -m piper -m en_US-lessac-medium -f out.wav -- 'Text'
```

Models: `en_US-lessac-*` (low/medium/high), plus ~40 languages. Repo:
`OHF-Voice/piper1-gpl` (GPL-3.0; the old `rhasspy/piper` is archived).

## Kokoro — best small model

```python
from kokoro import KPipeline
pipeline = KPipeline(lang_code="a")     # 'a' = American English
for gs, ps, audio in pipeline(text, voice="af_heart"):
    save(audio, "out.wav")
```

82M parameters, runs on CPU, faster than real-time.

## XTTS-v2 — cloning

```python
from TTS import TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
tts.tts_to_file(text="...", speaker_wav="reference.wav",
                language="en", file_path="out.wav")
```

## Reference audio rules

- 6–30 seconds
- Single speaker, no background noise, no music
- Natural speech, not shouting or whispering
- 24 kHz or higher, mono
- Consistent distance from the microphone

## Post-processing

```bash
ffmpeg -i vo.wav -af "highpass=f=80,acompressor=threshold=-18dB:ratio=3:attack=5:release=50" clean.wav
```

## Silence trimming

```bash
ffmpeg -i seg.wav -af "silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB:detection=peak" trim.wav
```
