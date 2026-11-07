# Headless API examples

## Queue, poll, download

```python
import json, uuid, time, urllib.request

BASE = "http://127.0.0.1:8188"

def queue(graph, client_id=None):
    client_id = client_id or str(uuid.uuid4())
    payload = json.dumps({"prompt": graph, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{BASE}/prompt", data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["prompt_id"]

def wait(prompt_id, timeout=1800):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with urllib.request.urlopen(f"{BASE}/history/{prompt_id}", timeout=10) as r:
            h = json.loads(r.read())
        if prompt_id in h:
            return h[prompt_id]
        time.sleep(1)
    raise TimeoutError(prompt_id)

def outputs(history, out_dir="out"):
    import os, urllib.parse
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for node in history.get("outputs", {}).values():
        for img in node.get("images", []):
            q = urllib.parse.urlencode({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img["type"],
            })
            dest = os.path.join(out_dir, img["filename"])
            urllib.request.urlretrieve(f"{BASE}/view?{q}", dest)
            paths.append(dest)
    return paths
```

## Discover node schemas — never guess an input name

```bash
curl -s http://127.0.0.1:8188/object_info/KSampler | python3 -m json.tool
```

## Batch over seeds

```python
import copy

def batch(graph, n, seed_base=0):
    results = []
    for i in range(n):
        g = copy.deepcopy(graph)
        for node in g.values():
            if node["class_type"] == "KSampler":
                node["inputs"]["seed"] = seed_base + i
        results.append(wait(queue(g)))
    return results
```

## Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/prompt` | POST | Queue a graph |
| `/history/{id}` | GET | Poll for results |
| `/view` | GET | Download an output file |
| `/object_info` | GET | Node class schemas |
| `/system_stats` | GET | VRAM and device info |
| `/queue` | GET | Current queue depth |
| `/interrupt` | POST | Cancel the running prompt |
