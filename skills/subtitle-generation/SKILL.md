---
name: subtitle-generation
description: Generate, time, and burn-in subtitles and captions using local open-source tools — whisper.cpp and faster-whisper for transcription, pysrt and WebVTT for timing, ffmpeg for burn-in, and ASS styling for word-level animated captions. Use when the user wants subtitles, captions, closed captions, transcript of a video, or accessible captioning.
metadata:
  promptSignals:
    phrases:
      - generate subtitles
      - add captions to video
      - burn in subtitles
      - whisper transcription
      - srt file
      - closed captions
      - video transcript
      - animated captions
      - word level subtitles
---

# Subtitle Generation

Transcribing audio and turning the result into subtitles that are actually
watchable. The transcription is the easy part; the timing, line breaking, and
styling are what make captions usable.

## Pipeline

```
audio/video → transcription (whisper) → SRT/VTT → styling → burn-in or sidecar
```

## Transcription

### whisper.cpp (CPU, fast, no Python deps)

```bash
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
cmake -B build && cmake --build build -j

# convert to 16kHz mono first
ffmpeg -i input.mp4 -ar 16000 -ac 1 audio16k.wav

./build/bin/whisper-cli -m models/ggml-base.bin -f audio16k.wav \
  -osrt -of output -l auto
```

Produces `output.srt`.

Model sizes: `tiny` 74MB, `base` 141MB, `small` 465MB, `medium` 1.5GB,
`large-v3` 3.0GB. `large-v3` is the most accurate; `base` is fine for clean
narration. Quantised builds (`-q5_0`, `-q8_0`) are also published and cut
the size roughly in half.

The CLI takes 16-bit WAV only, so convert first:

```bash
sh ./models/download-ggml-model.sh base
./build/bin/whisper-cli -m models/ggml-base.bin -f audio16k.wav \
  -osrt -of output -l auto
```

`-osrt` writes the SRT, `-of` sets the output filename prefix, and `-l auto`
detects the language.

### faster-whisper (Python, fastest on GPU)

```bash
pip install faster-whisper
```

```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")

segments, info = model.transcribe(
    "audio16k.wav",
    beam_size=5,
    vad_filter=True,              # skip silence — big speedup
    vad_parameters={"min_silence_duration_ms": 500},
    word_timestamps=True,         # needed for word-level captions
    initial_prompt="Product names, technical terms, and proper nouns.",
)

print(info.language, info.duration)

with open("out.srt", "w") as f:
    for i, seg in enumerate(segments, 1):
        line = f"{i}\n{seg.start:.3f} --> {seg.end:.3f}\n{seg.text.strip()}\n\n"
        print(line.strip())
        f.write(line)
```

**`initial_prompt` is the highest-leverage parameter.** Feeding it the
vocabulary of your video — brand names, jargon, spellings — dramatically
improves accuracy on exactly the words that matter.

`vad_filter=True` skips silence and is typically 3–5× faster.

### Word-level timestamps

```python
for seg in segments:
    for word in seg.words:
        print(f"{word.start:.2f}-{word.end:.2f}  {word.word}")
```

Use these for animated word-by-word captions.

## Caption quality rules

| Rule | Value |
|---|---|
| Characters per line | 42 (broadcast) / 32 (mobile) |
| Lines per caption | Max 2 |
| Reading speed | ≤ 17 characters per second |
| Minimum duration | 1.0s |
| Maximum duration | 7.0s |
| Gap between captions | 2 frames (80ms) |

```python
def split_caption(text, max_chars=42, max_lines=2):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines[:max_lines]
```

**Read speed check:**

```python
def cps(text, start, end):
    return len(text.replace(" ", "")) / max(end - start, 0.001)

# flag captions that flash too fast
if cps(cap_text, cap_start, cap_end) > 17:
    # extend the caption's end time
```

## Burn-in with ffmpeg

```bash
# simple white subtitles
ffmpeg -i input.mp4 -vf "subtitles=subs.srt" \
  -c:v libx264 -crf 18 -c:a copy out.mp4

# force the subtitle stream
ffmpeg -i input.mp4 -vf "subtitles=subs.srt:force_style='FontName=DejaVu Sans,Bold,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,Outline=2,MarginV=60'" \
  -c:v libx264 -crf 18 -c:a copy out.mp4
```

`force_style` uses ASS styling. Key fields: `FontName`, `FontSize`,
`PrimaryColour` (`&HAABBGGRR`), `OutlineColour`, `Outline`, `Shadow`,
`MarginV`, `Alignment` (2 = bottom centre, 5 = middle centre).

### Burning from an external file

```bash
ffmpeg -i input.mp4 -i subs.srt \
  -filter_complex "[0:v][1:s]overlay" \
  -c:v libx264 -crf 18 -c:a copy out.mp4
```

This avoids the `subtitles` filter's path-escaping problems.

## Animated word-by-word captions

Convert to ASS for karaoke-style highlighting:

```python
import re

def word_level_ass(segments, out="captions.ass", width=1080, height=1920):
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,DejaVu Sans,64,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,0,2,80,80,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def ts(t):
        h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
        return f"{h:d}:{m:02d}:{s:05.2f}"

    lines = [header]
    for seg in segments:
        if not seg.words: continue
        text = ""
        for w in seg.words:
            text += f"{{\\k{int(max(w.end - w.start, 0.05) * 100)}}}{w.word} "
        lines.append(f"Dialogue: 0,{ts(seg.start)},{ts(seg.end)},Main,,0,0,0,,{text.strip()}\\N")
    open(out, "w").write("\n".join(lines))
```

```bash
ffmpeg -i input.mp4 -vf "ass=captions.ass" -c:v libx264 -crf 18 -c:a copy out.mp4
```

`{\k<centiseconds>}` sets the per-word duration — the `SecondaryColour`
(`&H0000FFFF`, yellow) is what the active word shows in.

## Styling for vertical short-form

- **Position**: bottom third, not the very bottom. Platform UI covers the
  lower 15–20%.
- **Size**: 48–64px at 1080×1920.
- **Bold sans** with a 4px black outline, or a solid box behind.
- **Max 3 words per line**, 2 lines.
- **Highlight the active word** in a contrasting colour.
- **Never** place captions in the centre — they cover the subject's face.

## Sidecar vs burned-in

| Format | When |
|---|---|
| Burned-in | Social media, short-form, accessibility, autoplay |
| Sidecar `.srt` / `.vtt` | YouTube, courses, anything with a player |
| Both | YouTube with burned-in visuals plus a sidecar for search |

## Verifying a transcript

```bash
# spot-check timings against the video
ffmpeg -i input.mp4 -vf "subtitles=subs.srt" -t 10 -ss 5 out_check.mp4
```

Or export the transcript with timestamps for manual review:

```python
with open("transcript.txt", "w") as f:
    for seg in segments:
        f.write(f"[{seg.start:7.2f} → {seg.end:7.2f}] {seg.text.strip()}\n")
```

## Common failures

**Subtitles out of sync** — whisper worked on a resampled file with a different
duration than the video. Resample with `-ar 16000 -ac 1` and check the
durations match.

**Text too fast to read** — segments are too long. Use `vad_filter` and
`word_timestamps`, then split by reading speed rather than by model segments.

**Characters render as boxes** — the font is not installed. Check with
`fc-list | grep -i <name>` or use `FontName=DejaVu Sans`, which ships nearly
everywhere.

**Subtitles disappear in the encode** — the `subtitles` filter needs libass.
Check `ffmpeg -filters | grep subtitles`.

**Burned-in subtitles are blurry** — they were scaled up from a low-resolution
render. Generate at native resolution.

**`force_style` has no effect** — the subtitle file must be `.srt` or `.ass`;
ASS styling does not apply to WebVTT.

## Reference tools

Other open-source av pipeline tools worth knowing, each over 1,000
GitHub stars — see `references/av_pipeline-reference-tools.md`.

## Related skills

`local-tts-engines` · `video-translation-dubbing` · `lip-sync` ·
`long-to-short-repurpose` · `shorts-reels-pipeline` · `media-transcode-pipeline`
