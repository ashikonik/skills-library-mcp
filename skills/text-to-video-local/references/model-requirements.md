# Model requirements

## VRAM table

| Model | Params | Min VRAM | Length | Notes |
|---|---|---|---|---|
| Wan2.2 T2V-A14B | 14B | 24 GB | 5s @ 16fps | Best quality/size ratio |
| Wan2.2 T2V-A1B | 1.3B | 8 GB | 5s @ 16fps | Fast, lower quality |
| HunyuanVideo | 13B | 24 GB | 5s | Strong prompt adherence |
| LTX-Video | 2B | 16 GB | 10s | Fastest, good motion |
| CogVideoX-5B | 5B | 16 GB | 6s | Best for text rendering |
| AnimateDiff | 1.5B | 8 GB | 16s | Motion module on SD1.5 |
| CogVideoX-2B | 2B | 8 GB | 6s | Quantised |

## Quantisation

| Format | VRAM saving | Quality loss |
|---|---|---|
| fp16 | — | none |
| fp8 | ~45% | negligible |
| int8 | ~50% | slight detail loss |
| GGUF Q4 | ~70% | visible on textures |
| GGUF Q3 | ~75% | artefacts on fine detail |

Drop to fp8 before dropping to GGUF.

## Frame counts

Most video models require `length = 4n + 1`:

- 81 frames = 5s @ 16fps
- 121 frames = 7.5s @ 16fps
- 161 frames = 10s @ 16fps

## Prompt formula

```
[SUBJECT] + [ACTION] + [ENVIRONMENT] + [CAMERA] + [LIGHTING] + [STYLE]
```

Example:

```
a lone fisherman mending nets, wooden pier at dawn, wide shot, 35mm,
soft golden backlight, cinematic realism
```
