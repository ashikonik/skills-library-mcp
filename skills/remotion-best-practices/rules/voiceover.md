---
name: voiceover
description: Adding AI-generated voiceover to Remotion compositions using local TTS
metadata:
  tags: voiceover, audio, tts, speech, piper, calculateMetadata, dynamic duration
---

# Adding AI voiceover to a Remotion composition

Generate speech audio per scene with a local TTS engine, then use [`calculateMetadata`](./calculate-metadata) to dynamically size the composition to match the audio.

## Prerequisites

This guide uses a **local, open-source TTS engine** so nothing depends on a paid hosted API. Piper is the default; Coqui, Kokoro, and Bark work the same way.

If the user has not specified a TTS engine, recommend Piper — it is fast, runs on CPU, and its ONNX voices are easy to install. See the `local-tts-engines` skill for the full comparison, and `voice-cloning-rvc` if the voice must be cloned from a specific person.

Ensure the engine is installed before running the generation script:

```bash
# Piper
pip install piper-tts
# Kokoro (better quality, still local)
pip install kokoro
```

## Generating audio locally

Create a script that reads the config, synthesizes each scene's speech, and writes audio files to the `public/` directory so Remotion can access them via `staticFile()`.

Synthesizing with Piper from the command line:

```bash
echo "Welcome to the show." | piper \
  --model en_US-lessac-medium.onnx \
  --output_file public/voiceover/my-comp/scene-01-intro.wav
```

Or driving it from Node so the whole scene list is handled in one pass:

```ts title="generate-voiceover.ts"
import { execFile } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { promisify } from "node:util";

const run = promisify(execFile);

for (const scene of scenes) {
  const out = `public/voiceover/${compositionId}/${scene.id}.wav`;
  mkdirSync(`public/voiceover/${compositionId}`, { recursive: true });

  await run("piper", [
    "--model", "en_US-lessac-medium.onnx",
    "--output_file", out,
  ], { input: scene.text });

  console.log(`wrote ${out}`);
}
```

If you need a voice that is not one of the stock Piper voices, convert a reference clip to a speaker model with `voice-cloning-rvc` first and point the TTS step at that model.


## Dynamic composition duration with calculateMetadata

Use [`calculateMetadata`](./calculate-metadata.md) to measure the [audio durations](./get-audio-duration.md) and set the composition length accordingly.

```tsx
import { CalculateMetadataFunction, staticFile } from "remotion";
import { getAudioDuration } from "./get-audio-duration";

const FPS = 30;

const SCENE_AUDIO_FILES = [
  "voiceover/my-comp/scene-01-intro.mp3",
  "voiceover/my-comp/scene-02-main.mp3",
  "voiceover/my-comp/scene-03-outro.mp3",
];

export const calculateMetadata: CalculateMetadataFunction<Props> = async ({
  props,
}) => {
  const durations = await Promise.all(
    SCENE_AUDIO_FILES.map((file) => getAudioDuration(staticFile(file))),
  );

  const sceneDurations = durations.map((durationInSeconds) => {
    return durationInSeconds * FPS;
  });

  return {
    durationInFrames: Math.ceil(sceneDurations.reduce((sum, d) => sum + d, 0)),
  };
};
```

The computed `sceneDurations` are passed into the component via a `voiceover` prop so the component knows how long each scene should be.

If the composition uses [`<TransitionSeries>`](./transitions.md), subtract the overlap from total duration: [./transitions.md#calculating-total-composition-duration](./transitions.md#calculating-total-composition-duration)

## Rendering audio in the component

See [audio.md](./audio.md) for more information on how to render audio in the component.

## Delaying audio start

See [audio.md#delaying](./audio.md#delaying) for more information on how to delay the audio start.
