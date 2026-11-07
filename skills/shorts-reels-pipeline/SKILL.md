---
name: shorts-reels-pipeline
description: End-to-end pipeline for producing short-form vertical video (YouTube Shorts, TikTok, Instagram Reels) locally and with AI. Covers topic selection, script generation, TTS voiceover, stock or generated B-roll, auto-assembly with MoviePy or FFmpeg, caption burn-in, and multi-platform publishing. Use when the user wants to make a reel, a short, a TikTok, a Shorts video, or any vertical 9:16 social video.
metadata:
  promptSignals:
    phrases:
      - make a reel
      - make a short
      - tiktok video
      - youtube shorts
      - instagram reels
      - vertical video
      - short form video
      - viral video
      - 9:16 video
      - shorts pipeline
---

# Short-Form Vertical Video Pipeline

A repeatable pipeline from a topic to a published 9:16 video. Every stage has a
local, open-source option; nothing here requires a paid API.

## Why a dedicated pipeline

Short-form is not "video editing, but vertical". The format imposes hard
constraints that change every stage:

- **9:16 only** — 1080×1920, or 1920×1080 with crop. Plan for the crop.
- **Under 60 seconds** — retention is the product. The hook is the first 1.5s.
- **Sound-off default** — burned-in captions are mandatory, not optional.
- **One idea per video** — a topic, not a topic with a digression.

Generic video tools let you violate all of these silently. This skill enforces them.

## Pipeline stages

### 1. Topic and hook

Pick a topic with a visible payoff. Write **three** candidate hooks and pick
one — not the first one.

| Pattern | Example |
|---|---|
| Contrarian | "This is why your renders are slow" |
| Result-first | "60 seconds of cinematic B-roll, no camera" |
| Curiosity gap | "Nobody tells you this about vertical video" |
| Problem-solution | "Your captions are unreadable on mobile" |

The hook is spoken **and** on screen as text in the first 1.5 seconds. Both.

### 2. Script

Target 130–160 words for 60 seconds at natural pace (~150 wpm). Structure:

```
HOOK       0:00–0:03   one sentence, states the payoff
SETUP      0:03–0:10   minimal context, one sentence
BEAT 1     0:10–0:25   one idea
BEAT 2     0:25–0:45   one idea
PAYOFF     0:45–0:58   resolution, states the takeaway
```

Write it as spoken language. Read it aloud — anything you stumble over, rewrite.
See `script-and-story-editor` for longer-form script work.

### 3. Voiceover

Generate locally with `local-tts-engines`, or record. Keep the WAV at 44.1kHz
mono; the assembler handles conversion.

For a consistent channel voice, clone it once with `voice-cloning-rvc` and reuse
the model.

### 4. Visuals

Three sources, in descending preference:

1. **Stock footage** — fastest, most credible. See `stock-media-sourcing`.
2. **AI-generated** — `text-to-video-local` for model-rendered clips,
   `comfyui-video-workflows` for graph-driven generation.
3. **Screen capture** — for software/tool content. See `long-to-short-repurpose`.

Match cuts to script beats. Every visual should be a **vertical crop of
something interesting** — a face, a hand, a screen, a product detail. Generic
B-roll of empty scenery reads as filler on mobile.

### 5. Assembly

Two paths.

**MoviePy** — good when clips need per-frame logic:

```python
from moviepy.editor import VideoFileClip, concatenate_videoclips

clips = []
for path in shot_paths:
    c = VideoFileClip(path).resize(height=1920).crop(
        x_center=c.width/2, y_center=c.height/2, width=1080, height=1920)
    clips.append(c)

VideoFileClip(shot_paths[0]).audio.with_audio_channels(1) if False else None
final = concatenate_videoclips(clips, method="compose")
final.write_videofile("out.mp4", fps=30, codec="libx264", audio_codec="aac")
```

**FFmpeg** — good when clips are already sized correctly:

```bash
# concat a normalized sequence
for f in clips/*.mp4; do
  ffmpeg -y -i "$f" -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
    -r 30 -c:v libx264 -preset medium -crf 20 -c:a aac -ar 44100 "norm/$(basename "$f")"
done
ffmpeg -y -f concat -safe 0 -i norm/list.txt -c copy out.mp4
```

Always end with `-pix_fmt yuv420p` and `-movflags +faststart` for web playback.
See `media-transcode-pipeline` for the full encoding matrix.

### 6. Captions

Burn captions in — see `subtitle-generation`. Style rules for vertical:

- Bottom third, **not** the very bottom (platform UI covers the lower ~15%).
- Max 3 words per line, 2 lines max.
- Highlight the active word with a background box.
- Font: bold sans, 48–64px at 1080×1920.

### 7. Thumbnail and publish

Generate a thumbnail with `thumbnail-generator`. Then publish with
`social-publish-scheduling`.

## Platform specs

| Platform | Aspect | Length | Safe area |
|---|---|---|---|
| TikTok | 9:16 | up to 10 min (60s performs best) | avoid top 100px, bottom 320px, right 180px |
| Reels | 9:16 | up to 90s | avoid bottom 250px, right 180px |
| Shorts | 9:16 | up to 60s (up to 3 min) | avoid bottom 200px, right 180px |

## Common failures

**Captions overflow the safe area** → move up 250px; the platform UI covers the bottom.

**Audio too quiet on phones** → normalize to −14 LUFS, not −16. Phones play at
lower volume; −14 is the loudness target for social.

**Black bars despite cropping** → the crop must happen after scale. Use
`scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920`, not
`scale=1080:1920` alone.

**First frame is static** → the hook must land visually in frame 1. A black lead-in
loses 30%+ of viewers.

**Video rejected or muted** → some platforms auto-mute on upload. Verify the
audio track exists before publishing: `ffprobe -v error -show_streams out.mp4`.

## Reference tools

Other open-source video tools worth knowing, each over 1,000
GitHub stars — see `references/video-reference-tools.md`.

## Related skills

`local-tts-engines` · `stock-media-sourcing` · `text-to-video-local` ·
`subtitle-generation` · `thumbnail-generator` · `media-transcode-pipeline` ·
`social-publish-scheduling` · `long-to-short-repurpose` · `script-and-story-editor`
