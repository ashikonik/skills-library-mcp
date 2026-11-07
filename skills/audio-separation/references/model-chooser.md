# Choosing a separation model

| Model | Stems | Speed | Quality | VRAM |
|---|---|---|---|---|
| `htdemucs` | 4 | Medium | Good | 4 GB |
| `htdemucs_ft` | 4 | Slow | **Best** | 4 GB |
| `htdemucs_6s` | 6 | Medium | Adds piano, guitar | 5 GB |
| `mdx_extra` | 4 | Medium | Slightly better vocals | 4 GB |
| `mdx_extra_q` | 4 | Fast | Near-ft quality | 2 GB |
| `mdx_extra_q_16` | 4 | Fastest | Good | 2 GB |

## Commands

```bash
demucs --two-stems=vocals input.mp3          # instrumental + vocals
demucs -n htdemucs_ft input.mp3              # 4 stems, best quality
demucs -n htdemucs_6s input.mp3              # 6 stems
demucs --device cuda -n htdemucs input.mp3   # GPU
```

Output: `separated/htdemucs/<name>/{vocals,drums,bass,other}.wav`

## UVR models for karaoke quality

```bash
pip install "audio-separator[gpu]"
audio-separator song.mp3 --model_filename UVR-MDX-NET-Voc_FT.onnx \
  --output_dir isolated --output_format WAV
```

Single-model vocal isolation beats multi-stem separation for this task.

## Which tool for which job

| Job | Tool |
|---|---|
| Karaoke track | `demucs --two-stems=vocals` |
| Cleanest vocals | UVR MDX-Net Voc_FT |
| True instrumental | UVR DeEcho-DeReverb + instrumental |
| Tonal vs percussive | librosa HPSS (instant) |
| Sample extraction | Any of the above + pydub |

## Notes

- The 4-stem "instrumental" is drums + bass + other — not a true instrumental
- Separate once and keep the stems together; separate runs drift out of sync
- Artefacts in quiet passages are expected — lower the level instead
- Separation amplifies artefacts in already-compressed sources
