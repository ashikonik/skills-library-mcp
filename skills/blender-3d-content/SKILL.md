---
name: blender-3d-content
description: Create 3D content in Blender headlessly — product renders, animations, scene composition, exports to glTF/FBX/USD, and rendering stills or turntables with Cycles or EEVEE. Use when the user wants a 3D render, a product shot, a 3D asset, a turntable animation, or Blender automation.
metadata:
  promptSignals:
    phrases:
      - 3d render
      - blender script
      - product render
      - 3d model
      - turntable animation
      - blender headless
      - render a 3d scene
      - gltf export
      - 3d asset
---

# Blender 3D Content

Blender is a full 3D suite that runs headlessly and scriptably. That makes it the
most reliable way to get a *render* rather than a mockup — lighting, shadows,
reflections and materials are all real.

## Two ways in

| Approach | Use when |
|---|---|
| **Python API** (`bpy`) | Precise, repeatable, parametric. The default. |
| **MCP server** (`mcp-for-blender`) | An agent drives a live Blender session interactively |

The Python API covers everything. Reach for the MCP server only when the task
needs *interactive* adjustments — "make the camera lower", "change the material
to brushed steel" — with a human in the loop.

## Headless Python

```bash
blender --background --python script.py
```

## The Blender MCP bridge

```bash
# one command installs uv, the addon, and wires up your MCP clients
curl -LsSf https://www.mcp-for-blender.com/install.sh | sh

# or, if you already have uv:
uvx mcp-for-blender setup
```

The setup finds your MCP clients (Claude Desktop, Claude Code, Codex, Cursor,
VS Code, Devin Desktop/Windsurf, OpenCode, Antigravity), installs the Blender
addon, enables it, and backs up each config it touches. Restart your MCP
client afterwards — the addon starts its server when Blender opens.

The PyPI package was renamed from `blender-mcp` to **`mcp-for-blender`**.
Existing installs keep working and `uvx blender-mcp` still runs the server,
but new installs should use the new name.

### Minimal render script

```python
import bpy, math

# clear the default scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

# ground plane
bpy.ops.mesh.primitive_plane_add(size=20)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# subject
bpy.ops.mesh.primitive_monkey_add(location=(0, 0, 1))
bpy.ops.object.shade_smooth()

# three-point lighting
def area_light(name, loc, energy, size=5):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    # point it at the origin
    direction = (0, 0, 0.5) - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return obj

area_light("key",  (4, -4, 6), 1000)
area_light("fill", (-5, -2, 3), 300)
area_light("rim",  (0, 5, 4), 800)

# camera
cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (7, -7, 4)
cam.rotation_euler = (math.radians(65), 0, math.radians(45))
bpy.context.scene.camera = cam

# render
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.filepath = "out.png"
bpy.ops.render.render(write_still=True)
```

`to_track_quat('-Z', 'Y')` is the idiom for pointing a light or camera at a
target — it beats hand-computed Euler angles every time.

### Render engines

| Engine | Speed | Use for |
|---|---|---|
| `BLENDER_EEVEE_NEXT` | Seconds | Previews, social, motion graphics |
| `CYCLES` | Minutes–hours | Product shots, glass, caustics, realism |
| `BLENDER_WORKBENCH` | Instant | Silhouettes, clay renders, blocking |

Cycles with GPU:

```python
scene.render.engine = "CYCLES"
scene.cycles.device = "GPU"
scene.cycles.samples = 128
scene.cycles.use_denoising = True
```

`use_denoising` (OpenImageDenoise) is what makes 128 samples look like 4096.
Without it, grain ruins the render.

## Materials

Principled BSDF is the node every material is built on.

```python
mat = bpy.data.materials.new("BrushedSteel")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.6, 0.62, 0.65, 1)
bsdf.inputs["Metallic"].default_value = 1.0
bsdf.inputs["Roughness"].default_value = 0.35
bpy.context.object.data.materials.append(mat)
```

| Input | Range | Notes |
|---|---|---|
| Base Color | RGB | Albedo. Darkens with metallic. |
| Metallic | 0–1 | 1 = mirror; 0 = dielectric |
| Roughness | 0–1 | 0 = perfect mirror, 1 = matte |
| Alpha | 0–1 | Below 1 needs blend mode set |
| IOR | 1.45 default | Glass ~1.45, water 1.33 |

For **glass**: set Transmission to 1.0, Roughness ~0.05, and use Cycles —
EEVEE's refraction is an approximation.

## Product render recipe

1. **Grey seamless backdrop** — a plane with a curve swept into the background,
   or a large plane plus a world-coloured world.
2. **Three-point lighting** — key at 45°, fill at 1/3 key, rim behind.
3. **Area lights, not point lights** — point lights give hard hotspots.
4. **Studio HDRI** as world lighting for realistic reflections, or a solid
   world colour for flat product shots.
5. **Contact shadows** — Cycles gives these for free. In EEVEE enable
   `scene.eevee.use_shadows`.
6. **Camera at product height** — a 50mm-equivalent lens, `cam_data.lens = 50`,
   avoids the wide-angle distortion that makes renders look fake.

## Turntable animation

```python
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = 120
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = "frames/turn_"

# empty parent to orbit around
pivot = bpy.data.objects.new("Pivot", None)
bpy.context.collection.objects.link(pivot)
for obj in bpy.context.selected_objects:
    if obj.type == "MESH":
        obj.parent = pivot

for frame in range(scene.frame_start, scene.frame_end + 1):
    pivot.rotation_euler.z = 2 * math.pi * (frame - 1) / (scene.frame_end - 1)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)

# then assemble
subprocess.run(["ffmpeg", "-y", "-framerate", "30", "-i",
                "frames/turn_%04d.png", "-c:v", "libx264",
                "-crf", "18", "turntable.mp4"], check=True)
```

Better: render straight to video with `scene.render.image_settings.file_format =
'FFMPEG'` — no frame intermediate.

## Exporting assets

| Target | Command |
|---|---|
| glTF 2.0 | `bpy.ops.export_scene.gltf(filepath="out.glb", export_format="GLB")` |
| FBX | `bpy.ops.export_scene.fbx(filepath="out.fbx")` |
| USD | `bpy.ops.wm.usd_export(filepath="out.usdc")` |
| OBJ | `bpy.ops.wm.obj_export(filepath="out.obj")` |
| STL (print) | `bpy.ops.wm.stl_export(filepath="out.stl")` |

**GLB** for web and game engines, **FBX** for DCC interchange, **USD** for
large-scale VFX pipelines, **STL** for 3D printing.

Apply transforms before export, or scale/rotation is baked oddly:

```python
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
```

## Geometry from procedural sources

Blender can pull geometry in from elsewhere — useful when the shape matters more
than the model quality:

```python
# import an STL
bpy.ops.wm.stl_import(filepath="part.stl")

# add a modifier stack
bpy.ops.object.modifier_add(type="SUBSURF")
bpy.ops.object.modifier_add(type="BEVEL")
```

For hard-surface: Bevel (segments 3) → Subdivision (level 2) → Shade Auto Smooth.
That order is standard for product geometry.

## Text and logos in 3D

```python
bpy.ops.object.text_add(location=(0, 0, 0))
text = bpy.context.object
text.data.body = "BRAND"
text.data.extrude = 0.02      # give it depth
text.data.bevel_depth = 0.005
text.data.align_x = "CENTER"
```

Extrude is what makes text read as a physical object in a render.

## Common failures

**The render is empty/grey** — the camera is not set on the scene
(`scene.camera = cam`) or everything is outside the frustum. Print the camera
location and target it at the subject.

**Everything is too dark** — no world lighting. Set
`world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.05, 1)`
or add a fill light. Cycle renders need an environment.

**The render is noisy** — too few samples, or denoising is off. Raise
`samples` and keep `use_denoising = True`.

**Materials render black in Cycles** — a metal with no environment to reflect
is black. Add an HDRI world or a large soft light.

**"Cannot run, no GPU found"** — set `scene.cycles.device = "CPU"` and lower
samples, or enable GPU in Preferences → System.

**The animation is stuttering in the final video** — you rendered a still
sequence but encoded at the wrong frame rate. Match `scene.render.fps` to the
ffmpeg `-framerate`.

**Exported GLB has broken scale** — you didn't apply transforms. Run
`transform_apply` before export.

**The MCP server connects but Blender is not listening** — Blender must be
running with the addon enabled and the server started; the MCP side is only a
client.

## Reference tools

Other open-source 3d tools worth knowing, each over 1,000
GitHub stars — see `references/3d-reference-tools.md`.

## Related skills

`web-3d-asset-pipeline` · `blender-motion-state-inspection` ·
`thumbnail-generator` · `stock-media-sourcing` · `media-transcode-pipeline` ·
`comfyui-image-workflows`
