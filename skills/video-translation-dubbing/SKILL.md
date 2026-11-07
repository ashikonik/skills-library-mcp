---
name: video-translation-dubbing
description: Translate and dub video — transcribe, translate subtitles and dialogue, synthesize localized speech, align it to the original lip movement, and mix the result with the original audio. Covers Whisper, LLM translation, local TTS, forced alignment, voice cloning for consistent speakers, and lip-sync models like MuseTalk and LatentSync. Use when the user wants a video in another language, dubbed audio, translated subtitles, or a localized version of their content.
metadata:
  promptSignals:
    phrases:
      - dub a video
      - translate video
      - localize video
      - translate subtitles
      - other language version
      - dubbing
      - voice clone for dubbing
      - lip sync dubbing
      - multilingual video
---

# Video Translation & Dubbing

Localizing a video has four parts, and they have a strict order: **transcribe →
translate → synthesize → align**. Every failure in this pipeline comes from
skipping the alignment step.

## The pipeline

```
video → transcribe (whisper) → translate (LLM) → synthesize (TTS)
      → align timings → optional lip-sync → mix with original bed → mux
```

## 1. Transcribe with word timestamps

```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    "source.mp4",
    vad_filter=True,
    word_timestamps=True,       # required for alignment
    beam_size=5,
    initial_prompt="Product names, technical terms, and proper nouns.",
)
print(info.language, info.duration)
```

Keep the word timestamps — they are the only reliable way to know how long the
translated audio should be.

Also grab the audio as 16 kHz mono for the TTS alignment step:

```bash
ffmpeg -i source.mp4 -vn -ar 16000 -ac 1 source16k.wav
```

## 2. Translate

Translate **per segment**, not the whole transcript. Long context drifts, and
the model loses the speaker's voice.

```python
import json

def translate_segment(text: str, target_lang: str, glossary: dict) -> str:
    """Translate one segment, protecting proper nouns with placeholders."""
    protected = {}
    for i, term in enumerate(glossary):
        key = f"⟦{i}⟧"
        if term.lower() in text.lower():
            protected[key] = term
            text = text.replace(term, key)
    return text, protected
```

**Build a glossary** from brand names, product names, and jargon. A glossary
with twenty entries fixes more problems than any prompt tweak.

```
Term       →  Translation
────────   ──────────────
HunyuanVideo →  Video Hunyuan
SDXL         →  SDXL
Sora         →  Sora
```

Also decide explicitly, per project:

- **Tone**: formal, casual, or adapted to a register that sounds native
- **Length**: German and Finnish expand ~30% over English; Japanese contracts
  ~40%. The dub must fit the same slot.
- **Register**: do you translate profanity, or soften it?

## 3. Synthesize the dubbed audio

Generate **one file per segment** so a bad segment can be regenerated without
redoing the whole track.

```python
from TTS import TTS
import soundfile as sf

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)

segments_out = []
for i, (seg, translation) in enumerate(zip(segments, translations)):
    out = f"dub/seg_{i:03d}.wav"
    tts.tts_to_file(text=translation, speaker_wav="speaker_a.wav",
                    language="fr", file_path=out)
    segments_out.append(out)
```

For a multi-speaker video, **clone each speaker's voice** from a clean sample
of their original speech and keep one reference per speaker. See
`voice-cloning-rvc` for the cloning details and `local-tts-engines` for engine
selection.

## 4. Align — the critical step

The translated audio is a different length from the original. You have three
options, in increasing order of effort and quality.

### Option A — Time-stretch to fit (fast, robotic)

```bash
ffmpeg -y -i dub/seg_003.wav \
  -filter:a "atempo=1.08" \
  dub/seg_003_fit.wav
```

`atempo` accepts 0.5–2.0 per instance; chain it for larger factors:

```bash
# 2.4x speed = two atempo stages
-filter:a "atempo=1.2,atempo=2.0"
```

Beyond ±15% the speech sounds obviously synthetic. That is the practical
limit.

### Option B — Forced alignment against the original

Align the *source* transcript to the source audio, then align the
*translated* text to the *dubbed* audio, and derive the mapping.

```bash
# install
pip install montreal-forced-aligner

# align the dubbed audio against the translated text
mfa align dub/seg_003.wav translations/seg_003.txt french dub_mfa/seg_003
```

Montreal Forced Aligner produces a TextGrid with word-level timings. From
that you can compute the exact stretch factor per segment:

```python
def stretch_factor(src_dur: float, dub_dur: float) -> float:
    return dub_dur / src_dur if src_dur else 1.0

def atempo_chain(factor: float) -> str:
    """atempo only accepts 0.5-2.0; chain stages for larger factors."""
    stages = []
    remaining = factor
    while remaining > 2.0:
        stages.append("atempo=2.0")
        remaining /= 2.0
    stages.append(f"atempo={remaining:.4f}")
    return ",".join(stages)
```

### Option C — Lip-sync (best result)

When the speaker's mouth is visible, you must resynthesize the video frames
to match the new audio — otherwise the dub is wrong by definition. See
`lip-sync`.

## 5. Mix with the original audio

Keep the **original audio bed** (music, ambience, applause) under the dub. This
is what makes it sound like a dub rather than a replacement.

```bash
# 1. isolate music/ambience from the original
ffmpeg -y -i source.mp4 -vn \
  -af "highpass=f=200,lowpass=f=8000" \
  -c:a pcm_s16le bed.wav

# 2. duck the bed under the dub
ffmpeg -y -i dub_full.wav -i bed.wav -filter_complex \
  "[1:a][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[ducked];\
   [0:a][ducked]amix=inputs=2:duration=first:weights=1 0.25" \
  -c:a pcm_s16le mixed.wav
```

Levels: dub −16 LUFS, bed −26 LUFS, true peak −1.5 dBTP.

## 6. Mux and export

```bash
ffmpeg -y -i video_dubsync.mp4 -i mixed.wav \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -shortest \
  final.mp4
```

`-c:v copy` avoids a second generation loss. You only re-encode the video when
lip-sync changed the frames.

## Subtitle translation

A separate, much cheaper deliverable — no audio work at all.

```bash
# transcribe
whisper-cli -m models/ggml-large-v3.bin -f source16k.wav -osrt -of src

# translate the SRT
python translate_srt.py src.srt --target-lang de --glossary glossary.json -o de.srt

# burn in
ffmpeg -i source.mp4 -vf "subtitles=de.srt:force_style='FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,Outline=2,MarginV=60'" \
  -c:v libx264 -crf 18 -c:a copy source_de.mp4
```

```python
import re, json

TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")

def parse_srt(text: str) -> list[dict]:
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) < 2: continue
        m = TIMESTAMP_RE.search(b)
        if not m: continue
        g = [int(x) for x in m.groups()]
        start = g[0]*3600 + g[1]*60 + g[2] + g[3]/1000
        end   = g[4]*3600 + g[5]*60 + g[6] + g[7]/1000
        out.append({"index": lines[0], "start": start, "end": end,
                    "text": "\n".join(lines[2:])})
    return out

def to_srt(entries: list[dict]) -> str:
    def ts(t):
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s%1)*1000)):03d}"
    blocks = []
    for i, e in enumerate(entries, 1):
        blocks.append(f"{i}\n{ts(e['start'])} --> {ts(e['end'])}\n{e['text']}")
    return "\n\n".join(blocks) + "\n"
```

**Re-time after translation.** German subtitle lines are longer and take longer
to read. Keep the original timings only if the translated text has a similar
character count; otherwise split the cue and extend the end time.

```python
def retime(entry: dict, cps_limit: float = 17.0) -> list[dict]:
    chars = len(entry["text"].replace(" ", ""))
    dur = entry["end"] - entry["start"]
    if chars / dur <= cps_limit:
        return [entry]
    # split into two cues of roughly equal length
    words = entry["text"].split()
    half = len(words) // 2
    mid = entry["start"] + dur * 0.5
    return [
        {**entry, "end": mid, "text": " ".join(words[:half])},
        {**entry, "start": mid,  "text": " ".join(words[half:])},
    ]
```

## End-to-end script

```python
import subprocess, os, json
from faster_whisper import WhisperModel

os.makedirs("work", exist_ok=True)

# 1. transcribe
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, _ = model.transcribe("source.mp4", vad_filter=True,
                               word_timestamps=True)

# 2. translate
translations = []
for seg in segments:
    text = seg.text.strip()
    translated = llm_translate(text, target_lang="es", glossary=GLOSSARY)
    translations.append(translated)

# 3. synthesize
for i, t in enumerate(translations):
    tts.tts_to_file(text=t, speaker_wav=SPEAKERS[i % len(SPEAKERS)],
                    language="es", file_path=f"work/seg_{i:03d}.wav")

# 4. time-stretch each segment to its original slot
for i, (seg, path) in enumerate(zip(segments, sorted(glob("work/seg_*.wav")))):
    src_dur = seg.end - seg.start
    dub_dur = duration(path)
    factor = dub_dur / src_dur
    if abs(factor - 1.0) > 0.02:
        subprocess.run(["ffmpeg", "-y", "-i", path, "-filter:a",
                        atempo_chain(factor), f"work/fit_{i:03d}.wav"], check=True)
    else:
        shutil.copy(path, f"work/fit_{i:03d}.wav")

# 5. concatenate with gaps matching the original pauses
# 6. mix with the original bed
# 7. mux
```

## Common failures

**The dub is too long for the shot** — no length constraint was applied. Use
Option B or C, or rewrite the translation to be shorter. Atempo alone past
15% is audibly bad.

**The mouth moves but the words are different** — you did not lip-sync. Run
MuseTalk/LatentSync on the speaker's shots.

**The voice sounds nothing like the original speaker** — you used a generic
voice. Clone per speaker and keep one reference per speaker across all
segments. See `voice-cloning-rvc`.

**The translation is wrong in a specific term** — no glossary. Build one and
protect the terms with placeholders.

**Subtitles desync after translation** — timings were copied without
re-timing. Re-time by reading speed.

**The dub is clipped or the music drowns it** — levels. Dub −16 LUFS, bed
−26 LUFS.

**Silence in the middle of a segment** — TTS generated a trailing pause.
Trim leading/trailing silence before concatenating:

```bash
ffmpeg -y -i seg.wav -af "silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB:detection=peak" trimmed.wav
```

**Different speakers sound identical** — you used one reference for all
segments. Map each segment to its speaker.

**A cultural reference was translated literally** — this needs a human pass.
Translation quality has a ceiling; flag segments that need review rather than
shipping them silently.

**Rights** — you need the rights to the original footage, the music, and the
voices. Dubbing someone else's content without permission is not
repurposing.

## Reference tools

Other open-source av pipeline tools worth knowing, each over 1,000
GitHub stars — see `references/av_pipeline-reference-tools.md`.

## Related skills

`lip-sync` · `voice-cloning-rvc` · `local-tts-engines` ·
`subtitle-generation` · `audio-separation` · `media-transcode-pipeline` ·
`long-to-short-repurpose`
