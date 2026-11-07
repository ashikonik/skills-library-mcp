---
name: tts-to-video
description: Compose a complete video from a script by generating a voiceover with local TTS, timing visuals to the audio, and assembling the result — including script-to-shot planning, forced alignment, audio-driven video length, and background music mixing. Use when the user wants to turn a script or text into a narrated video, make an explainer, or produce a video with a synthetic voice.
metadata:
  promptSignals:
    phrases:
      - script to video
      - turn a script into a video
      - narrated video
      - make an explainer video
      - voiceover video
      - sync visuals to audio
      - text to narrated video
---

# Script to Narrated Video

The composition problem: you have words and you have pictures, and they have to
agree on timing. This skill covers going from a script to a finished narrated
video.

## The core idea

**Let the audio drive.** Generate the voiceover first, measure its duration, then
build visuals to fit — rather than building a video and trying to fit narration
into it. This inverts the usual order and eliminates most sync problems.

```
script → TTS voiceover → measure duration → plan shots → generate/find visuals →
        assemble → captions → music → mix
```

## 1. Write the script for speech

Spoken word has different rules than written word.

| Written | Spoken |
|---|---|
| Semicolons | Full stops |
| "utilize" | "use" |
| Parentheticals | Cut them |
| Bullets | Convert to sentences |
| Numbers: "1,250" | "twelve hundred fifty" or "one thousand two hundred fifty" |
| Symbols: &, %, @ | "and", "percent", "at" |

Read it aloud at a natural pace. Target ~150 words per minute for narration,
~130 for explainers where you want breathing room.

```python
words = len(script.split())
duration_estimate = words / 150 * 60   # seconds
```

## 2. Generate the voiceover

See `local-tts-engines` for engine choice. Practical notes for video:

- Generate **one file per paragraph or sentence**, not the whole script. Long
  generations drift and are hard to re-edit.
- Keep a consistent reference voice across segments so it does not shift.

```python
from TTS import TTS

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
segments = []
for i, para in enumerate(paragraphs):
    out = f"vo/seg_{i:03d}.wav"
    tts.tts_to_file(text=para, speaker_wav="reference.wav",
                    language="en", file_path=out, split_sentences=True)
    segments.append(out)
```

## 3. Measure and align

```bash
# concatenate with a small gap between paragraphs
for f in vo/seg_*.wav; do echo "file '$f'"; done > list.txt
ffmpeg -y -f concat -safe 0 -i list.txt -c:a pcm_s16le vo_full.wav
```

Then build a timing map — the offset of each segment within the full audio.
This is what lets you place visuals against the right words.

```python
import wave, os

def durations(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()

segments = []
offset = 0.0
GAP = 0.35   # seconds between paragraphs

for path in sorted(glob.glob("vo/seg_*.wav")):
    d = durations(path)
    segments.append({"path": path, "start": offset, "end": offset + d})
    offset += d + GAP
total = offset
```

**Word-level alignment** is better when you want captions or word-highlighted
captions. Use whisper with `word_timestamps=True` against the final mixed
audio — see `subtitle-generation`.

## 4. Plan shots against the audio

Split the narration into beats, then assign a visual to each beat.

```python
# a beat is a sentence or clause; aim for 2-6 seconds each
import re

def beats(text, max_chars=180):
    parts = re.split(r"(?<=[.!?])\s+", text)
    out, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 1 > max_chars and cur:
            out.append(cur.strip())
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur: out.append(cur.strip())
    return out
```

| Narration length | Visual |
|---|---|
| < 2s | Single establishing shot or B-roll |
| 2–5s | One visual, may move within frame |
| 5–10s | Two visuals, or one with a cutaway |
| > 10s | Multiple visuals, or a visual with an overlay |

**Cut on meaning, not on a timer.** Cutting every 3 seconds regardless of
content is what makes AI-edited video feel cheap.

## 5. Assemble

```python
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

audio = AudioFileClip("vo_full.wav")
clips = []
for seg in shots:
    c = VideoFileClip(seg["path"]).resize(height=1920).crop(
        x_center=c.width/2, y_center=c.height/2, width=1080, height=1920)
    # trim/pad to the segment duration
    c = c.subclipped(0, min(c.duration, seg["duration"]))
    if c.duration < seg["duration"]:
        c = c.with_duration(seg["duration"])
    clips.append(c)

video = concatenate_videoclips(clips, method="compose")
video = video.with_audio(audio).with_duration(audio.duration)
video.write_videofile("out.mp4", fps=30, codec="libx264", audio_codec="aac")
```

The `with_duration` padding is what keeps the video and audio from drifting
apart. Without it, each clip's actual duration wins and the narration
desynchronises by the second clip.

## 6. Captions

Generate from the final audio with `subtitle-generation`. Do this **after**
mixing, so the timings match what viewers hear.

## 7. Music and mixing

```bash
# duck music under the narration
ffmpeg -i music.wav -i vo_full.wav -filter_complex \
  "[0:a][1:a]sidechaincompress=threshold=0.03:ratio=8:attack=5:release=300[ducked];\
[1:a][ducked]amix=inputs=2:duration=first:weights=1 0.5" \
  mixed.wav
```

Levels: narration −16 LUFS, music bed −24 LUFS, true peak −1.5 dBTP.

## 8. Export

```bash
ffmpeg -y -i out.mp4 \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart \
  final.mp4
```

See `media-transcode-pipeline` for platform-specific variants.

## Common failures

**Audio and video drift apart** — clips were not padded to their segment
durations. Use `with_duration`.

**The voice changes mid-video** — the TTS was run per sentence without a
consistent reference, or the engine does not support cross-sentence
consistency. Use one reference and one model.

**Videos are the wrong length** — you built the video first and forced audio
to fit. Reverse the order.

**Captions do not match the words** — captions were generated before the final
mix. Regenerate after mixing.

**Music masks the narration** — the ducking threshold is too high. Lower
`threshold` to 0.02 and raise `ratio` to 10.

**Awkward pacing** — shots are timed mechanically. Cut on sentence boundaries
instead.

## Related skills

`local-tts-engines` · `shorts-reels-pipeline` · `subtitle-generation` ·
`music-generation` · `stock-media-sourcing` · `text-to-video-local` ·
`media-transcode-pipeline` · `script-and-story-editor`
