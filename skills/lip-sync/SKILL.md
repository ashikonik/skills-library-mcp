---
name: lip-sync
description: Sync mouth movement to audio in video using local open-source models — MuseTalk, LatentSync, Wav2Lip, and VideoRetalking — with installation, performance comparison, audio preprocessing requirements, and artefact fixes. Use when the user wants lip sync, needs a talking avatar, wants to dub a video, or needs mouth movements to match a voice track.
metadata:
  promptSignals:
    phrases:
      - lip sync
      - lipsync
      - sync mouth to audio
      - talking avatar
      - wav2lip
      - musetalk
      - latentsync
      - dub a video
      - make the character talk
---

# Lip Sync

Making mouth movements match an audio track. The hard part is that a face
rotating through 3D produces very different mouth shapes than a flat frontal
face — most models only work on near-frontal shots.

## Model comparison

| Model | Repo | Quality | Speed | Works on | Notes |
|---|---|---|---|---|---|
| **MuseTalk** | `TMElyralab/MuseTalk` | Very good | Real-time (30fps+) | 256px face crops | Best quality/speed ratio. Real-time. |
| **LatentSync** | `bytedance/LatentSync` | Excellent | Slow | Full frame, varied angles | Diffusion-based, best quality. |
| **Wav2Lip** | `Rudrabha/Wav2Lip` | Good | Fast | Near-frontal only | The original. Still widely used. |
| **VideoRetalking** | `Rudrabha/VideoRetalking` | Good | Moderate | Near-frontal | Better teeth/mouth region than Wav2Lip |
| **SadTalker** | `OpenTalker/SadTalker` | Moderate | Fast | Portrait stills | Talking head from a photo |

**MuseTalk for real-time work. LatentSync for final quality.**

## MuseTalk

```bash
git clone https://github.com/TMElyralab/MuseTalk.git
cd MuseTalk
pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
  --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

MuseTalk ships shell wrappers that handle the model and config wiring for
you — use these first:

```bash
sh inference.sh v1.5 normal     # batch inference (MuseTalk 1.5)
sh inference.sh v1.5 realtime   # real-time inference
sh inference.sh v1.0 normal     # the older model
```

ffmpeg must be installed and on `PATH` before running any of these.

The underlying module takes the **paths from a YAML config**, not from
command-line flags:

```bash
python -m scripts.inference \
  --inference_config configs/inference/test.yaml \
  --unet_model_path models/musetalkV15/unet.pth \
  --unet_config models/musetalkV15/musetalk.json \
  --version v15 \
  --bbox_shift 0 \
  --result_dir results/
```

Real-time mode is a separate module:

```bash
python -m scripts.realtime_inference \
  --inference_config configs/inference/realtime.yaml \
  --unet_model_path models/musetalkV15/unet.pth \
  --unet_config models/musetalkV15/musetalk.json \
  --version v15 --fps 25 \
  --result_dir results/realtime/
```

`bbox_shift` moves the detected mouth region. Use `-1` or `1` when the mouth
alignment is slightly off — a frequent fix for detection failures. Other
useful flags: `--use_float16` (faster), `--batch_size`, `--parsing_mode`
(`jaw` by default), and `--use_saved_coord` / `--saved_coord` to cache face
detections across runs.

```yaml
# configs/inference/test.yaml — the paths live here, not in the command line
inference_mode: "streaming"
bbox_shift: 0
audio_padding_length: 2
audio_padding_left: 0
audio_padding_right: 0
fps: 25
results_dir: "results/"
audio_path: "data/video/yongen.mp3"
video_path: "data/video/yongen.mp4"
```

**Audio must be 16kHz mono WAV.** Convert first:

```bash
ffmpeg -i voice.mp3 -ar 16000 -ac 1 voice16k.wav
```

## LatentSync

```bash
git clone https://github.com/bytedance/LatentSync.git
cd LatentSync
conda create -n latentsync python=3.10 -y
conda activate latentsync
pip install -e .
```

Checkpoints come from HuggingFace:

```bash
huggingface-cli download ByteDance/LatentSync-1.6 \
  latentsync_unet.pt --local-dir checkpoints
huggingface-cli download ByteDance/LatentSync-1.6 \
  whisper/tiny.pt --local-dir checkpoints
```

```bash
python scripts/inference.py \
  --unet_config_path configs/unet/stage2.yaml \
  --inference_ckpt_path checkpoints/latentsync_unet.pt \
  --video_path input.mp4 \
  --audio_path input.wav \
  --video_out_path out.mp4 \
  --inference_steps 20 \
  --guidance_scale 1.5
```

The repo ships an `inference.sh` that wires this up against the demo assets,
and `gradio_app.py` for a UI. The config path selects the resolution tier:
`stage2.yaml` (256px), `stage2_512.yaml` (512px), `stage2_efficient.yaml`
(20GB VRAM, slight quality loss — the one for consumer GPUs like the 3090).

`inference_steps` takes 20–50; higher is better quality and slower.
`guidance_scale` takes 1.0–3.0; higher follows the audio more tightly but can
distort or jitter. `--enable_deepcache` speeds up generation.

**VRAM for inference:** 8GB with LatentSync 1.5, 18GB with LatentSync 1.6.

## Wav2Lip

```bash
git clone https://github.com/Rudrabha/Wav2Lip.git
cd Wav2Lip
pip install -r requirements.txt
```

The SFD face detector weights must be downloaded to
`face_detection/detection/sfd/s3fd.pth` before running.

```bash
python inference.py \
  --checkpoint_path checkpoints/wav2lip_gan.pth \
  --face input.mp4 \
  --audio voice16k.wav \
  --outfile results/out.mp4
```

Face detection happens inline — there is no separate detection step. Two flags
fix most bad output:

- `--pads 0 20 0 0` — pads the detected face box. Increase the bottom pad to
  include the chin; this often fixes a misplaced mouth.
- `--nosmooth` — turn off detection smoothing. Use this when you see two
  mouths or a dislocated mouth region.

`--resize_factor` lowers the working resolution, which can look better on
720p than on 1080p because the models were trained on smaller faces.
`--static` + `--fps` handles a still image instead of a video.

## Audio preprocessing

Every lip-sync model expects the same thing. Do this first.

```bash
# 16kHz mono WAV
ffmpeg -i voice.mp3 -ar 16000 -ac 1 voice16k.wav

# trim silence at both ends (models lip-sync silence badly)
ffmpeg -i voice16k.wav \
  -af "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-45dB,\
areverse,silenceremove=start_periods=1:start_duration=0.1:start_threshold=-45dB,areverse" \
  trimmed.wav

# normalise level
ffmpeg -i trimmed.wav -af loudnorm=I=-16:TP=-1.5 LRA=11 final.wav
```

**Video requirements:**
- The audio must be **shorter than or equal to** the video. Lip-sync tools
  either stop early or loop badly.
- 25 or 30 fps. Mismatched fps causes drift.
- The face should be **large in frame** — at least 200px tall.
- Near-frontal, minimal head rotation, mouth not occluded.

```bash
ffmpeg -i input.mp4 -i final.wav -c:v copy -c:a aac -shortest synced.mp4
```

Check the durations match:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 input.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 final.wav
```

## Performance

MuseTalk is the only one close to real time on consumer hardware.

| VRAM | Model | Practical speed |
|---|---|---|
| 6GB | MuseTalk | ~10–20 fps |
| 8GB | MuseTalk | ~30 fps (real-time) |
| 12GB | MuseTalk | real-time, larger batch |
| 16GB+ | LatentSync | 3–8 fps |
| 24GB | LatentSync | ~10 fps with tiling |

LatentSync's resolution tier is selected by the config path — `stage2.yaml`
(256px) is cheap, `stage2_512.yaml` (512px) is the high-resolution path and
costs more VRAM:

```bash
python scripts/inference.py \
  --unet_config_path configs/unet/stage2_512.yaml \
  --inference_ckpt_path checkpoints/latentsync_unet.pt \
  --video_path input.mp4 --audio_path input.wav \
  --video_out_path out.mp4 \
  --inference_steps 20 --enable_deepcache
```

On a consumer GPU use `configs/unet/stage2_efficient.yaml` instead — it needs
20GB rather than 30GB, at a slight cost in visual quality and temporal
consistency.

## Artefact fixes

| Symptom | Cause | Fix |
|---|---|---|
| Mouth doesn't move | Audio not 16kHz mono | Resample first |
| Mouth moves out of sync | fps mismatch or silence padding | Match fps exactly; trim silence |
| Blurry mouth region | Model resolution limit | MuseTalk at 256px is native; do not upscale first |
| Teeth artefacts | Wav2Lip on a low-resolution face | Crop tighter, or use MuseTalk |
| Face flickers | Detection instability | Use SFD face detector, set `bbox_shift` |
| Output has a black border | Source aspect ratio | Crop the source to the face first |
| Only lips move, jaw frozen | Model limitation | Expected for most; MuseTalk handles jaw better |

## Compositing

To replace only the mouth region over the original video:

```bash
ffmpeg -i original.mp4 -i lipsynced.mp4 \
  -filter_complex "[0:v][1:v]overlay=shortest=1" \
  -c:v libx264 -crf 18 -pix_fmt yuv420p final.mp4
```

Both videos must be the same resolution and fps, or the overlay will shift.

## Legal and ethical note

Cloning a face or voice without consent is unlawful in many jurisdictions and
is universally wrong. Get explicit permission, and disclose synthetic media
where it could mislead. See `voice-cloning-rvc` for the consent rules.

## Reference tools

Other open-source audio tools worth knowing, each over 1,000
GitHub stars — see `references/audio-reference-tools.md`.

## Related skills

`voice-cloning-rvc` · `local-tts-engines` · `video-background-removal` ·
`video-translation-dubbing` · `tts-to-video`
