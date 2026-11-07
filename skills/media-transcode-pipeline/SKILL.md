---
name: media-transcode-pipeline
description: Transcode and package video, audio and images for every platform — H.264/H.265/AV1 and VP9 encodes, bitrate ladders, loudness normalisation, resolution ladders, thumbnails, sprite sheets, streaming manifests and ffmpeg presets. Use when the user needs platform-specific exports, to compress video, to build adaptive bitrate ladders, or to normalise audio loudness.
metadata:
  promptSignals:
    phrases:
      - transcode video
      - compress video
      - export for youtube
      - export for instagram
      - convert to mp4
      - h265 encode
      - av1 encode
      - normalize audio loudness
      - bitrate ladder
      - create thumbnails
      - streaming manifest
---

# Media Transcode Pipeline

Transcoding is where a master render becomes a deliverable. The decisions are
codec, bitrate, resolution, loudness, and container — and each platform has its
own answer.

## Codec selection

| Codec | Size | Speed | Use for |
|---|---|---|---|
| **H.264** (`libx264`) | Baseline | Fast | Universal — the safe default |
| **H.265** (`libx265`) | ~40% smaller than H.264 | Slow | Archive, high-quality delivery |
| **VP9** (`libvpx-vp9`) | ~30% smaller than H.264 | Very slow | Web (YouTube, WebM) |
| **AV1** (`libsvtav1`) | ~50% smaller than H.264 | Slow | Bandwidth-constrained streaming |
| **ProRes** (`prores_ks`) | Huge | Fast | Intermediate editing masters |
| **DNxHR** | Huge | Fast | Intermediate editing masters (Windows) |

**Default to H.264.** A file that plays everywhere beats a file that is 30%
smaller and does not play on half the devices your audience uses.

## Platform export presets

| Platform | Container | Video | Audio | Max size | Notes |
|---|---|---|---|---|---|
| YouTube | MP4 | H.264, CRF 18–23 | AAC 384k | 256 GB | Source quality preferred |
| Instagram Reels | MP4 | H.264, ≤ 4.5 Mbps | AAC 128k | 4 GB | 1080×1920 |
| TikTok | MP4 | H.264, ≤ 10 Mbps | AAC 128k | 4 GB | 1080×1920 |
| Twitter/X | MP4 | H.264, ≤ 5 Mbps | AAC 128k | 512 MB | 1280×720 min |
| Facebook | MP4 | H.264, ≤ 4 Mbps | AAC 128k | 4 GB | |
| LinkedIn | MP4 | H.264, ≤ 5 Mbps | AAC 128k | 5 GB | 1:1 or 16:9 |
| WhatsApp | MP4 | H.264 | AAC 96k | 16 MB | Aggressive compression |
| Web (MP4) | MP4 | H.264 + faststart | AAC 128k | | `+faststart` required |

## The canonical command

```bash
ffmpeg -y -i master.mov \
  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
  -profile:v high -level 4.0 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart \
  out.mp4
```

Every part of that matters:

| Flag | Why |
|---|---|
| `-pix_fmt yuv420p` | Required for playback everywhere; yuv444p breaks browsers and phones |
| `-preset slow` | ~2× smaller than `medium` at the same CRF, for free wall-clock |
| `-movflags +faststart` | Moves the index to the front so playback starts before the file downloads |
| `-ar 48000` | 48 kHz is the standard; 44.1 kHz triggers a resample |
| `-profile:v high -level 4.0` | Widest hardware decoder support |

## Bitrate targeting

CRF (constant quality) is right for VOD. CBR (constant bitrate) is right when
you need a hard size ceiling or a live pipeline.

```bash
# VBV-constrained CRF — gives you CRF quality AND a max bitrate
ffmpeg -i in.mp4 -c:v libx264 -preset slow -crf 20 \
  -maxrate 8M -bufsize 16M \
  -c:a aac -b:a 192k out.mp4
```

The `-bufsize` should be twice `-maxrate`. A 1 Mbit/s buffer with an 8 Mbit/s
ceiling causes stalls; a 16 Mbit/s buffer does not.

Size estimate:

```
size_MB ≈ (video_bitrate_Mbps + audio_bitrate_Mbps) × duration_s / 8
```

A 60-second Reel at 4.5 Mbps video + 128 kbps audio ≈ 35 MB.

## Resolution ladder

```bash
for res in 2160 1440 1080 720 480; do
  ffmpeg -y -i master.mp4 \
    -vf "scale=-2:${res}" \
    -c:v libx264 -preset slow -crf 21 \
    -c:a aac -b:a 128k \
    "out_${res}p.mp4"
done
```

`-2` keeps the aspect ratio and makes the dimension even — **always use `-2`,
never a hard number**, because odd dimensions fail in H.264.

## Adaptive bitrate ladder (ABR)

```bash
MASTER=master.mp4
mkdir -p hls
ffmpeg -y -i "$MASTER" \
  -filter_complex "[0:v]split=3[v1][v2][v3];\
[v1]scale=w=1920:h=1080:force_original_aspect_ratio=decrease[v1out];\
[v2]scale=w=1280:h=720:force_original_aspect_ratio=decrease[v2out];\
[v3]scale=w=854:h=480:force_original_aspect_ratio=decrease[v3out]" \
  -map "[v1out]" -c:v:0 libx264 -b:v:0 5000k -maxrate:v0 5350k -bufsize:v0 7500k \
  -map "[v2out]" -c:v:1 libx264 -b:v:1 3000k -maxrate:v1 3200k -bufsize:v1 4500k \
  -map "[v3out]" -c:v:2 libx264 -b:v:2 1000k -maxrate:v2 1100k -bufsize:v2 1500k \
  -map a:0 -c:a aac -b:a 128k -ac 2 \
  -f hls -hls_time 6 -hls_playlist_type vod \
  -master_pl_name master.m3u8 \
  -var_stream_map "v:0,a:0,name:1080p v:1,a:0,name:720p v:2,a:0,name:480p" \
  hls/%v/stream.m3u8
```

`-hls_time 6` gives 6-second segments, `-hls_playlist_type vod` writes a
complete playlist with all segments listed (not a live sliding window).

## Loudness normalisation

Broadcast standard is **−24 LUFS** (EBU R128) for broadcast, **−16 LUFS** for
streaming/social, **−14 LUFS** for music.

```bash
# single-pass loudnorm (fast, good enough)
ffmpeg -i in.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11 out.mp4

# two-pass (exact)
ffmpeg -i in.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2> log.txt
# paste the measured values back:
ffmpeg -i in.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11:
  measured_I=-20.3:measured_TP=-3.1:measured_LRA=6.2:
  measured_thresh=-30.5:offset=0.9:linear=true:print_format=summary out.mp4
```

**True peak matters more than LUFS.** A file at −16 LUFS with peaks at 0 dBFS
distorts on every phone. Cap true peak at −1.5 dBTP.

## Thumbnails

```bash
# a frame at 10 seconds
ffmpeg -y -ss 10 -i master.mp4 -vframes 1 -q:v 2 thumb.jpg

# several candidates
ffmpeg -y -i master.mp4 -vf "fps=1/10,scale=640:-2" -q:v 3 cand_%02d.jpg

# contact sheet
ffmpeg -y -i master.mp4 -vf "fps=1/30,scale=320:-2,tile=4x4" -frames:v 1 sheet.jpg
```

`-q:v 2` is high-quality JPEG (2 is near-lossless, 31 is worst). PNG for
graphics, JPEG for photos.

## Sprite sheets (for scrubbing previews)

```bash
ffmpeg -y -i master.mp4 -vf "fps=1,scale=160:-2,tile=10x10" -frames:v 1 sprites.png
```

## Image outputs

```bash
# PNG sequence from video
ffmpeg -y -i master.mp4 frames/frame_%05d.png

# animated GIF (palette is the hard part)
ffmpeg -y -i master.mp4 -vf "fps=15,scale=480:-1:flags=lanczos,palettegen" pal.png
ffmpeg -y -i master.mp4 -i pal.png -lavfi "fps=15,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse" out.gif

# WebP
ffmpeg -y -i master.mp4 -c:v libwebp -quality 80 -loop 0 out.webp
```

The two-pass `palettegen`/`paletteuse` chain is what stops GIFs from looking
like a 256-colour disaster.

## Hardware acceleration

```bash
# NVENC (NVIDIA)
ffmpeg -i in.mp4 -c:v h264_nvenc -preset p5 -cq 22 -b:v 0 out.mp4

# QSV (Intel)
ffmpeg -i in.mp4 -c:v h264_qsv -global_quality 22 out.mp4

# VAAPI (AMD)
ffmpeg -i in.mp4 -c:v h264_vaapi -vaapi_device /dev/dri/renderD128 \
  -vf 'format=nv12,hwupload' -qp 22 out.mp4
```

`-b:v 0` with `-cq` puts NVENC in constant-quality mode. Hardware encodes are
5–10× faster but less efficient than x264/x265 at the same quality — use them
for speed, not for final masters.

## Batch pipeline

```python
import subprocess, os, json

PRESETS = {
    "youtube":   dict(vb="8000k", maxrate="8560k", res="1920", ab="384k"),
    "reels":     dict(vb="4500k", maxrate="4800k", res="1920", ab="128k"),
    "twitter":   dict(vb="5000k", maxrate="5350k", res="1280", ab="128k"),
}

def export(master: str, out_dir: str, presets=PRESETS) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    results = {}
    for name, p in presets.items():
        out = os.path.join(out_dir, f"{name}.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", master,
            "-vf", f"scale=-2:{p['res']}",
            "-c:v", "libx264", "-preset", "slow",
            "-b:v", p["vb"], "-maxrate", p["maxrate"],
            "-bufsize", p["maxrate"],
            "-c:a", "aac", "-b:a", p["ab"], "-ar", "48000",
            "-movflags", "+faststart", "-pix_fmt", "yuv420p",
            out,
        ]
        subprocess.run(cmd, check=True)
        results[name] = out
    return results
```

## Probing

```bash
ffprobe -v quiet -print_format json -show_format -show_streams in.mp4
```

```python
import json, subprocess

def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)

def summarize(path: str) -> str:
    d = probe(path)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    dur = float(d["format"]["duration"])
    size_mb = int(d["format"]["size"]) / 1e6
    return (f"{v['width']}x{v['height']} {v['codec_name']} "
            f"{dur:.1f}s {size_mb:.1f}MB "
            f"audio={a['codec_name'] if a else 'none'}")
```

Always probe the output after transcoding. A silent stream, a zero-duration
file, and a mismatched aspect ratio all pass a `check=True` ffmpeg run.

## Common failures

**"Invalid data found when processing input"** — the file is not a video, or
the codec is not compiled in. `ffmpeg -codecs | grep <codec>`.

**No audio in the output** — the source had no audio stream, or you mapped
wrong. Check `ffprobe` and add `-map 0:a?` (the `?` makes it optional).

**"Height not divisible by 2"** — odd height. Use `scale=-2:1080`, never
`scale=1920:1080`.

**The output plays but the audio is out of sync** — you changed the video
framerate without touching the audio. Keep both at the source rate, or
regenerate the audio.

**The file is huge** — CRF is too low, or the preset is too fast. Try
`-crf 23 -preset slow` and compare. Also check you did not leave `-b:v 0`.

**It plays in Premiere but not in a browser** — missing `-pix_fmt yuv420p`,
or the profile/level is too high. Add `-profile:v high -level 4.0`.

**The browser buffers the whole file before playing** — missing
`-movflags +faststart`.

**A 4-minute GIF is 90 MB** — you are not using the palette pass, and the
frame rate is too high. Use 15 fps and a 480px width.

**x265 is absurdly slow or out of memory** — x265 spawns a thread pool sized
to the core count. Limit it: `-x265-params "pools=4:frame-threads=2"`.

**The audio is clipped** — true peak above 0 dBFS. Apply `loudnorm` with
`TP=-1.5`.

**Transcode lost quality in a second pass** — you encoded an already-encoded
file. Always transcode from the master.

## Reference tools

Other open-source av pipeline tools worth knowing, each over 1,000
GitHub stars — see `references/av_pipeline-reference-tools.md`.

## Related skills

`tts-to-video` · `shorts-reels-pipeline` · `long-to-short-repurpose` ·
`subtitle-generation` · `video-translation-dubbing` · `audio-separation` ·
`thumbnail-generator`
