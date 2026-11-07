---
name: video-upscale-interpolate
description: Upscale video resolution and increase frame rate using local open-source tools — Real-ESRGAN, video2x, Waifu2x, and RIFE frame interpolation — including tiling for large videos, model selection, batch processing, and artifact avoidance. Use when the user wants to upscale a video, improve resolution, make a video smoother, increase FPS, or convert 24fps to 60fps.
metadata:
  promptSignals:
    phrases:
      - upscale video
      - video super resolution
      - increase frame rate
      - 24fps to 60fps
      - frame interpolation
      - real esrgan video
      - video2x
      - rife interpolation
      - make video smoother
      - 4k video
---

# Video Upscaling and Frame Interpolation

Two separate operations that are often confused:

- **Upscaling** raises resolution (720p → 4K). Adds detail.
- **Frame interpolation** raises frame rate (24fps → 60fps). Adds motion
  smoothness. Does not add detail.

They compose: upscale first, then interpolate, because interpolation needs good
frames to interpolate between.

## Tool selection

| Tool | Upscale | Interpolate | Notes |
|---|---|---|---|
| [video2x](https://github.com/k4yt3x/video2x) | ✅ | ✅ (RIFE) | Wraps both. Simplest combined path. AGPL-3.0. |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | ✅ | ❌ | Best photo/detail quality. BSD-3-Clause. |
| [Waifu2x](https://github.com/AaronFeng753/Waifu2x-Extension-GUI) | ✅ | ✅ | Strong on anime/illustration. |
| [RIFE](https://github.com/hzwer/ECCV2022-RIFE) | ❌ | ✅ | Best interpolation quality. MIT. |
| [Real-ESRGAN-ncnn](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan) | ✅ | ❌ | Single binary, no Python. Easiest install. |

**Use the ncnn Vulkan build if you just need results** — no Python environment,
no CUDA setup.

## Real-ESRGAN via ncnn (fastest path)

```bash
# download the release binary for your platform, then:
realesrgan-ncnn-vulkan -i input.jpg -o output.png -s 4 -n realesrgan-x4plus
```

The ncnn build takes **images or directories of images** — not video. `-f`
selects the output *image* format (`jpg`/`png`/`webp`), not a video codec.
For video, extract frames first and reassemble after:

```bash
ffmpeg -i input.mp4 -vsync 0 frames/%05d.png
realesrgan-ncnn-vulkan -i frames -o out_frames -s 4 -n realesrgan-x4plus
ffmpeg -framerate 24 -i out_frames/%05d.png -c:v libx264 -crf 16 -pix_fmt yuv420p out_4k.mp4
```

| Flag | Meaning |
|---|---|
| `-s` | Scale factor: 2, 3, or 4. Default 4. |
| `-n` | Model name: `realesr-animevideov3`, `realesrgan-x4plus`, `realesrgan-x4plus-anime`, `realesrnet-x4plus`. |
| `-t` | Tile size (≥32). `0` = auto. Smaller uses less VRAM. |
| `-m` | Folder holding the model weights. Default `models`. |
| `-g` | GPU id. Default auto. |
| `-j` | Thread counts as `load:proc:save`, e.g. `2:2:2`. |
| `-x` | Enable test-time augmentation (slower, cleaner). |

## video2x (upscale + interpolate together)

Video2X 6.0 is a complete C/C++ rewrite — it is no longer a Python package.
Install the prebuilt binary or GUI installer from the releases page (Windows
and Linux). It needs a **Vulkan**-capable GPU and a CPU with AVX2.

There are no subcommands. You pick a processor with `-p`:

```bash
# upscale 4x with Real-ESRGAN
video2x -i input.mp4 -o output.mp4 -p realesrgan -s 4 \
  --realesrgan-model realesrgan-plus

# interpolate 4x with RIFE
video2x -i input.mp4 -o output.mp4 -p rife -m 4 --rife-model rife-v4.6

# upscale to an exact resolution with Anime4K (libplacebo)
video2x -i input.mp4 -o output.mp4 -w 3840 -h 2160 -p libplacebo \
  --libplacebo-shader anime4k-v4-a+a
```

| Flag | Meaning |
|---|---|
| `-i` / `-o` | Input and output video paths (both required). |
| `-p` | Processor: `libplacebo`, `realesrgan`, `realcugan`, `rife`. |
| `-s` | Scaling factor (minimum 2). Upscaling only. |
| `-w` / `-h` | Exact output width and height. Upscaling only. |
| `-m` | Frame rate multiplier (minimum 2). Interpolation only. |
| `-n` | Noise level. Upscaling only. |
| `-t` | Scene-detection threshold, 0–100. Interpolation only. |
| `-c` | Output codec. Default `libx264`. |
| `-e` | Extra encoder option as `key=value`, repeatable. |
| `-d` | Vulkan device index (GPU id). |
| `-a` | Hardware-accelerated decoding. Default `none`. |
| `-b` | Benchmark mode — discards frames and reports average FPS. |
| `--list-gpus` | List available GPUs and exit. |

`--realesrgan-model` accepts `realesr-animevideov3`, `realesrgan-plus-anime`,
`realesrgan-plus`, `realesr-generalv3`. `--rife-model` accepts `rife`,
`rife-HD`, `rife-UHD`, `rife-anime`, `rife-v2` through `rife-v4.26`; the
default is `rife-v4.26`.

**Upscaling and interpolation are separate runs** in 6.0 — there is no
"hybrid" mode any more. Run one, then the other.

## Model selection

| Model | Use for |
|---|---|
| `realesrgan-plus` | General footage, photographic content |
| `realesrgan-plus-anime` | Anime, illustration, line art |
| `realesr-animevideov3` | Video-tuned; the ncnn and video2x default |
| `realesr-generalv3` | Adjustable denoise; good on compressed source |
| `rife-v4.26` | Interpolation; the video2x default |
| `rife-v4.6` | Earlier interpolation model |
| `rife-v3.1` | Faster, slightly less stable on motion |

## Tiling for large videos

Upscaling a 4K frame to 8K needs far more VRAM than the whole frame at 4K.
Tile it — with the ncnn build:

```bash
realesrgan-ncnn-vulkan -i frames -o out_frames -s 2 \
  -t 512 -m realesr-general-x4v3   # 512px tiles
```

`-t 0` (the default) picks the tile size automatically. Smaller tiles use
less VRAM but can produce visible seams. 512 is a good balance; 256 if you
OOM, 1024 if you have VRAM to spare.

## Interpolation with RIFE

Via video2x (recommended — the ncnn/Vulkan build is fast and handles video
directly):

```bash
# 24fps -> 48fps
video2x -i in.mp4 -o out_48.mp4 -p rife -m 2

# 24fps -> 96fps
video2x -i in.mp4 -o out_96.mp4 -p rife -m 4 --rife-model rife-v4.6
```

Or with the upstream RIFE repo (`hzwer/ECCV2022-RIFE`, MIT) directly:

```bash
python3 inference_video.py --exp=2 --video=video.mp4
```

`--exp` is the frame rate multiplier — `1` doubles, `2` quadruples. The
output lands next to the input as `video_2X_xxfps.mp4`. Other useful flags:

| Flag | Meaning |
|---|---|
| `--exp=N` | Frame rate multiplier. |
| `--fps=N` | Target frame rate for the output. |
| `--scale=0.5` | Optical-flow processing resolution. Use 0.5 for 4K sources; 2.0 if you get disordered patterns. |
| `--output=path` | Output path. |
| `--montage --png` | Write frames as PNGs instead of a video. |
| `--img=dir/` | Interpolate a directory of images. |

For image pairs:

```bash
python3 inference_img.py --img img0.png img1.png --exp=4
```

For 60fps from 24fps you need a 2.5× multiplier, which `--exp` cannot
express — use `--fps=60` instead, interpolate by 3 and drop frames, or let
video2x handle it.

`-t` on video2x sets the scene-detection threshold (0–100). Lower values
detect scene cuts more aggressively, which prevents smearing across a cut.

## Frame-by-frame with Real-ESRGAN (Python)

```python
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer
from basicsr.utils import imwrite
import cv2, glob, os

model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                 num_block=23, num_grow_ch=32, scale=4)
upsampler = RealESRGANer(
    scale=4, model_path="weights/RealESRGAN_x4plus.pth", model=model,
    tile=512, tile_pad=10, pre_pad=0, half=True)

for path in sorted(glob.glob("frames/*.png")):
    img = cv2.imread(path)
    out, _ = upsampler.enhance(img, outscale=4)
    imwrite(out, os.path.join("out_frames", os.path.basename(path)))
```

Then reassemble:

```bash
ffmpeg -y -framerate 24 -i out_frames/%05d.png -c:v libx264 -crf 16 -pix_fmt yuv420p out.mp4
```

**Preserve the original frame rate** when reassembling. If the source was
24fps and you write at 30fps, the motion speeds up.

## Order of operations

```
source (720p, 24fps)
  → upscale ×2 or ×4        (Real-ESRGAN, tiled)
  → interpolate to 48/60fps (RIFE)
  → encode                   (see media-transcode-pipeline)
```

Do not interpolate before upscaling — RIFE interpolates between source frames,
and low-resolution source frames yield low-resolution interpolated frames.

## Artifact avoidance

**Warping / ghosting** — the classic interpolation failure on fast motion.
Fix: use a newer RIFE (`v4.6`), or reduce the multiplier to 2.0.

**Shimmer on edges** — temporal inconsistency in the upscaler. Use
`realesr-general-x4v3` with denoise rather than `x4plus`, or upscale without
interpolation.

**Flicker between frames** — the source is already compressed badly. Upscaling
cannot restore information that is not there. Re-encode the source cleanly first
at a high bitrate, then upscale.

**Detail too sharp, plastic look** — the model is over-sharpening. Use
`x2plus` instead of `x4plus`, or denoise first.

## Common failures

**OOM** — enable tiling (`-t 256`), use the ncnn build, or process in chunks.

**Output video plays at wrong speed** — you changed the frame rate during
reassembly. Keep it identical to the source.

**Colours shift after upscale** — the upscaler works in YUV; convert RGB→YUV
with the correct matrix before processing, or use the ncnn build which handles
this internally.

**Very slow on CPU** — expected. Real-ESRGAN on video is minutes per second of
footage. Use the ncnn Vulkan build with `--gpu` if supported.

## Related skills

`text-to-video-local` · `comfyui-video-workflows` · `media-transcode-pipeline` ·
`video-background-removal` · `shorts-reels-pipeline`
