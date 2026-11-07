# Lip-sync model comparison

| Model | Input | Output quality | Speed | VRAM | Notes |
|---|---|---|---|---|---|
| MuseTalk | Video/image | Good | Real-time | 8 GB | Best balance |
| LatentSync | Video | Very good | Slow | 16 GB | Diffusion, best fidelity |
| Wav2Lip | Video | Fair | Fast | 4 GB | Universal fallback |
| VideoRetalking | Video | Good | Slow | 12 GB | Can retarget head pose |
| SadTalker | Still image | Good | Medium | 6 GB | Portrait animation |

## Audio requirements

Every model needs:

- 16 kHz mono WAV
- Peak-normalised to about -3 dBFS
- No leading or trailing silence

```bash
ffmpeg -y -i new_audio.mp3 -ar 16000 -ac 1 -c:a pcm_s16le audio16k.wav
ffmpeg -y -i audio16k.wav \
  -af "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-50dB:detection=peak" \
  -af "loudnorm=I=-20:TP=-3:LRA=11" audio_ready.wav
```

## Diagnostic table

| Symptom | Cause | Fix |
|---|---|---|
| Mouth lags | Window too short | Raise `audio_padding_length` |
| Mouth leads | Audio offset | Shift the audio |
| Blurry mouth | Wav2Lip | Switch to MuseTalk/LatentSync |
| Edge artefacts | Bad face box | Pass bbox manually |
| Flicker | Chunk boundaries | Overlap and blend chunks |
| Unchanged mouth | Model ignored the input | Check the audio actually changed |

## Performance

| Hardware | MuseTalk | LatentSync |
|---|---|---|
| RTX 3060 12GB | ~1.5x realtime | ~0.3x realtime |
| RTX 4090 24GB | ~4x realtime | ~0.8x realtime |
| A100 40GB | ~8x realtime | ~2x realtime |
