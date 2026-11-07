# Core node reference

## Loading models

| Node class | Output slots | Use |
|---|---|---|
| `CheckpointLoaderSimple` | 0=MODEL, 1=CLIP, 2=VAE | SD1.5, SDXL |
| `UNETLoader` | 0=MODEL | FLUX, SD3 |
| `DualCLIPLoader` | 0=CLIP | FLUX (t5xxl + clip_l) |
| `VAELoader` | 0=VAE | FLUX ae.sft |
| `LoraLoader` | 0=MODEL, 1=CLIP | SDXL, FLUX |

## Conditioning

| Node | Purpose |
|---|---|
| `CLIPTextEncode` | SDXL positive/negative |
| `CLIPTextEncodeFlux` | FLUX positive (no negative) |
| `ConditioningSetArea` | Regional prompting |
| `ConditioningCombine` | Merge conditionings |
| `ControlNetApplyAdvanced` | Spatial control |
| `IPAdapterAdvanced` | Reference image conditioning |

## Sampling

| Node | Purpose |
|---|---|
| `KSampler` | Standard |
| `KSamplerAdvanced` | Custom start/end steps, add noise |
| `SamplerCustom` | Full control |
| `EmptyLatentImage` | Latent space source |

## Output

| Node | Purpose |
|---|---|
| `VAEDecode` | Latent to pixels |
| `VAEDecodeTiled` | Low-VRAM decode |
| `SaveImage` | Write PNG |
| `PreviewImage` | Show without saving |

## Model placement

FLUX needs three files:

```
models/unet/flux1-dev-fp8.safetensors
models/clip/t5xxl_fp8.safetensors
models/clip/clip_l.safetensors
models/vae/ae.sft
```

A `CheckpointLoaderSimple` pointed at the FLUX file will fail — FLUX is not
a single-file checkpoint.
