---
name: comfyui-video-workflows
description: Build and run ComfyUI workflows for video generation and animation, including Wan and LTX-Video model wrappers, graph structure, custom node installation, workflow JSON authoring, and the ComfyUI API for headless batch generation. Use when the user works with ComfyUI graphs, wants to automate ComfyUI, or needs to generate video through a node-based pipeline.
metadata:
  promptSignals:
    phrases:
      - comfyui workflow
      - comfyui graph
      - automate comfyui
      - comfyui api
      - wan video wrapper
      - ltx video comfyui
      - custom nodes
      - comfyui batch render
---

# ComfyUI Video Workflows

ComfyUI is a node graph over diffusion models. For video it is the most flexible
option available locally: the graph can hold a model, a conditioning, a scheduler,
a VAE, and a video output stage, and you can swap any of them.

## Install

```bash
git clone https://github.com/Comfy-Org/ComfyUI.git
cd ComfyUI
python -m pip install -r requirements.txt
python main.py
```

For video, install the model wrapper custom nodes:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git
git clone https://github.com/city96/ComfyUI-GGUF.git          # quantized Wan
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git  # image conditioning
```

Use `ComfyUI-Manager` for the rest — it handles installs and dependency
resolution for most nodes:

```bash
git clone https://github.com/Comfy-Org/ComfyUI-Manager.git
```

## Graph structure for video

A minimal text-to-video graph:

```
UNETLoader ──┐
              ├─→ ModelSamplingSD3 ──→ KSampler ──→ VAEDecode ──→ SaveAnimatedWEBP
CLIPLoader ───┘        (or KSampler with CFG)         │
  └─→ CLIPTextEncode ──→ Conditioning ────────────────┘
CLIPLoader (llama) ──→ CLIPTextEncode ──→ Conditioning (positive)

VideoCombine node: takes frame batch → mp4/webp/gif
```

Key differences from image graphs:

1. **The VAE decodes a frame batch, not a single latent.** Use a 3D VAE for
   temporal consistency — Wan and LTX both ship one.
2. **Sampler output is a latent batch.** `VideoCombine` writes the frames.
3. **Image conditioning replaces some text.** For image-to-video, an
   `IPAdapter` or `LoadImage` + `VAEEncode` branch feeds the first frame.

## Models to use

| Task | Model | Notes |
|---|---|---|
| Text→video | Wan2.1/T2V-1.3B | Low VRAM, good starting point |
| Text→video (quality) | Wan2.2 14B | Needs 24GB+, or GGUF quantized |
| Image→video | Wan I2V, LTX-Video | First-frame conditioning |
| Long video / interpolation | LTX-Video | Fastest iteration |
| Animation from stills | AnimateDiff + SD1.5 | Huge LoRA ecosystem |

## Headless batch generation via the API

ComfyUI serves a JSON API. This is how you make it reproducible and scriptable.

```python
import json, uuid, time, urllib.request

HOST = "http://127.0.0.1:8188"

def queue_prompt(workflow: dict) -> str:
    prompt_id = str(uuid.uuid4())
    body = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{HOST}/prompt", data=body, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req).read()
    return prompt_id

def wait_for(prompt_id: str, timeout=1800):
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{HOST}/history/{prompt_id}") as r:
            hist = json.loads(r.read())
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(2)
    raise TimeoutError(prompt_id)

def download(prompt_id, filename):
    with urllib.request.urlopen(f"{HOST}/view?filename={filename}") as r:
        open(f"out/{filename}", "wb").write(r.read())
```

The workflow dict is the graph in API format — node id → `{class_type, inputs}`.
Export it from the ComfyUI UI via **Save (API Format)** so you get the exact
JSON, then parameterise the prompt text node's inputs.

## Parameterising a workflow

```python
workflow = json.load(open("workflows/wan_t2v_api.json"))

node_id = "6"   # the CLIPTextEncode node holding the positive prompt
workflow[node_id]["inputs"]["text"] = "a slow push-in on a lighthouse at dusk"

prompt_id = queue_prompt(workflow)
hist = wait_for(prompt_id)
```

## Workflow JSON authoring

Export via **Save (API Format)** — not "Save", which produces the GUI format with
node positions that the API ignores.

Structure:

```json
{
  "3": {
    "class_type": "KSampler",
    "inputs": {
      "seed": 12345,
      "steps": 30,
      "cfg": 6.0,
      "sampler_name": "uni_pc",
      "scheduler": "simple",
      "denoise": 1.0,
      "model": ["4", 0],
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["5", 0]
    }
  }
}
```

Links are `[node_id, output_index]`.

## Custom node hygiene

- Pin versions. A node that updates its `requirements.txt` can break your graph.
  Use the ComfyUI-Manager version lock or `git checkout <sha>` in each node dir.
- Custom nodes run arbitrary code. Only install from repos you have read.
- Many video nodes need `--highvram` or `--normalvram` flags. On 8–16GB cards,
  start with `--lowvram`.

## Common failures

**Temporal flicker** — the 3D VAE is not being used, or the sampler is
single-image. Use a video VAE and a video-capable sampler.

**OOM during decode** — the latent batch is being decoded all at once. Decode in
chunks, or reduce frame count. `video2x` and `Real-ESRGAN` also need tiled
inference at high resolutions.

**Graph loads but produces a black video** — `VideoCombine` frame rate is 0, or
the output path is relative to a different ComfyUI working directory. Use an
absolute path.

**Node missing at load** — the custom node's folder name does not match its
`NODE_CLASS_MAPPINGS` keys, or the node failed to import. Check the ComfyUI
console on startup.

## Related skills

`text-to-video-local` · `comfyui-image-workflows` · `video-upscale-interpolate` ·
`local-diffusion-suite` · `media-transcode-pipeline` · `shorts-reels-pipeline`
