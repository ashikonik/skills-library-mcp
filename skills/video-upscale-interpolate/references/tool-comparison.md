# Upscale and interpolation tools

## Upscalers

| Tool | Speed | Best for | Command |
|---|---|---|---|
| Real-ESRGAN | Medium | General photos, anime | `realesrgan -i in.png -o out.png -n realesrgan-x4plus -s 4` |
| Real-ESRGAN (4x-UltraSharp) | Medium | Sharp photos | `realesrgan -i in.png -o out.png -n 4x-UltraSharp -s 4` |
| video2x | Medium | Video (frames) | `video2x -i in.mp4 -o out.mp4 -m realesrgan` |
| Waifu2x | Fast | Anime / line art | `waifu2x -i in.png -o out.png -s 2` |
| Topaz Video AI | Fast | Best quality (closed source) | GUI only |

## Interpolators

| Tool | Multiplier | Notes |
|---|---|---|
| RIFE | 2x-4x | Best general, `rife-ncnn-vulkan` |
| FILM | 2x | Fast, good on slow motion |
| DAIN | 2x | Slow, artefacts on fast motion |
| ffmpeg `minterpolate` | 2x | Built in, mediocre |

## Order of operations

1. **Interpolate first**, then upscale. Upscaling then interpolating
   interpolates artefacts.
2. Upscale with tiling on large frames to fit VRAM.
3. Match the frame rate at the end — the output should be `original_fps *
   multiplier`.

## Tiling

```bash
python realesrgan_realtime.py \
  -i in.mp4 -o out.mp4 \
  -n 4x-UltraSharp -s 4 \
  --tile 256 --tile_pad 10 \
  --fps 30
```

Without `--tile`, a 4K frame will OOM on most GPUs.
