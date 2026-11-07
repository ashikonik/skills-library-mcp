# Platform delivery specs

| Platform | Container | Video | Audio | Max size | Notes |
|---|---|---|---|---|---|
| YouTube | MP4 | H.264 CRF 18-23 | AAC 384k | 256 GB | Source quality preferred |
| Instagram Reels | MP4 | H.264 <= 4.5 Mbps | AAC 128k | 4 GB | 1080x1920 |
| TikTok | MP4 | H.264 <= 10 Mbps | AAC 128k | 4 GB | 1080x1920 |
| Twitter/X | MP4 | H.264 <= 5 Mbps | AAC 128k | 512 MB | 1280x720 min |
| Facebook | MP4 | H.264 <= 4 Mbps | AAC 128k | 4 GB | |
| LinkedIn | MP4 | H.264 <= 5 Mbps | AAC 128k | 5 GB | 1:1 or 16:9 |
| WhatsApp | MP4 | H.264 | AAC 96k | 16 MB | Aggressive compression |
| Web | MP4 | H.264 + faststart | AAC 128k | — | `+faststart` required |

## Canonical command

```bash
ffmpeg -y -i master.mov \
  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
  -profile:v high -level 4.0 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -movflags +faststart \
  out.mp4
```

## Loudness

| Deliverable | Integrated | True peak |
|---|---|---|
| Social / streaming | -16 LUFS | -1.5 dBTP |
| Broadcast (EBU R128) | -24 LUFS | -2 dBTP |
| Music | -14 LUFS | -1 dBTP |

## Codecs

| Codec | Size vs H.264 | Speed | Use |
|---|---|---|---|
| H.264 | baseline | Fast | Universal default |
| H.265 | -40% | Slow | Archive |
| VP9 | -30% | Very slow | Web |
| AV1 | -50% | Slow | Constrained streaming |
| ProRes | Huge | Fast | Editing master |

## HLS ladder

`-hls_time 6`, `-hls_playlist_type vod`, `-master_pl_name master.m3u8`,
`-var_stream_map` naming each rendition.
