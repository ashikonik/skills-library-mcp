# Platform presets

Copy-paste ffmpeg commands per platform. Always end with `-movflags +faststart`
and `-pix_fmt yuv420p`.

## Instagram Reels / TikTok / YouTube Shorts (1080x1920)

```bash
ffmpeg -y -i source.mp4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -ar 48000 -movflags +faststart reel.mp4
```

## Twitter/X (1280x720, 5 Mbps cap)

```bash
ffmpeg -y -i source.mp4 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease" \
  -c:v libx264 -preset slow -b:v 5000k -maxrate 5350k -bufsize 5350k \
  -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart tweet.mp4
```

## LinkedIn (1280x720, 5 Mbps cap)

Same as Twitter but `-b:v 4500k`.

## Safe areas

| Platform | Top | Bottom | Right |
|---|---|---|---|
| TikTok | 180px | 320px | 120px |
| Reels | 180px | 420px | 120px |
| Shorts | 180px | 320px | 180px |
| LinkedIn | 180px | 260px | 260px |

Keep text inside these bounds. The rest is covered by platform UI.
