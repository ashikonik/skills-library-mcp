# Local diffusion suite comparison

| Tool | Models | GUI | API | Best for |
|---|---|---|---|---|
| AUTOMATIC1111 | SD1.5, SDXL | Yes | Yes | Extensibility, huge plugin set |
| Forge | SD1.5, SDXL | Yes | Yes | A1111 fork, faster, less VRAM |
| InvokeAI | SDXL, FLUX | Yes | Yes | Node workflow, pro retouching |
| Fooocus | SDXL | Yes | No | Fast, opinionated defaults |
| ComfyUI | SDXL, FLUX, WAN | Yes | Yes | Graphs, video, automation |
| diffusers | All | No | Python | Scripting, research |

## VRAM by model

| Model | fp16 | fp8 | int8 | GGUF Q4 |
|---|---|---|---|---|
| SD 1.5 | 4 GB | 3 GB | 2.5 GB | 2 GB |
| SDXL | 8 GB | 6 GB | 5 GB | 4 GB |
| SDXL Lightning | 6 GB | 5 GB | 4 GB | 3.5 GB |
| FLUX.1 dev | 24 GB | 16 GB | 12 GB | 8 GB |
| FLUX.1 schnell | 16 GB | 10 GB | 8 GB | 6 GB |

## Sampler defaults

| Model | Sampler | Scheduler | Steps | CFG |
|---|---|---|---|---|
| SDXL | dpmpp_2m | karras | 25-30 | 5-7 |
| SDXL base | euler_a | normal | 28-35 | 7 |
| FLUX | euler | simple | 20-25 | 1.0-3.5 |
| FLUX distilled | euler | simple | 4-8 | 1.0 |

FLUX ignores the negative prompt in most distilled checkpoints — do not spend
effort on it there.

## Speedups

- `--fast` (A1111) → `--fastaccel`
- xformers or SDP attention
- TAESD preview
- Tiled VAE decode for large images
- Generate at native resolution, upscale later
