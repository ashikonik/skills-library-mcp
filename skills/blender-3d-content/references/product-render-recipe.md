# Product render recipe

## Setup

1. Grey seamless backdrop (swept plane or large plane + dark world)
2. Three-point lighting: key at 45deg, fill at 1/3 key, rim behind
3. Area lights, not point lights — point lights give hard hotspots
4. Studio HDRI as world lighting for realistic reflections
5. Camera at product height, 50mm equivalent

## Three-point lighting in Python

```python
import math

def area_light(name, loc, energy, size=5, target=(0, 0, 0.5)):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return obj

area_light("key",  (4, -4, 6), 1000, size=4)
area_light("fill", (-5, -2, 3), 300,  size=6)
area_light("rim",  (0, 5, 4),  800,  size=3)
```

## Cycles settings

```python
scene.render.engine = "CYCLES"
scene.cycles.device = "GPU"
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.cycles.transmission_bounces = 8   # for glass
```

`use_denoising` is what makes 128 samples look like 4096.

## Principled BSDF inputs

| Input | Range | Notes |
|---|---|---|
| Base Color | RGB | Albedo |
| Metallic | 0-1 | 1 = mirror |
| Roughness | 0-1 | 0 = mirror, 1 = matte |
| Alpha | 0-1 | Below 1 needs blend mode |
| IOR | 1.45 default | Glass 1.45, water 1.33 |
| Transmission | 0-1 | 1 = glass, needs Cycles |

## Export

| Target | Command |
|---|---|
| glTF | `bpy.ops.export_scene.gltf(filepath="out.glb", export_format="GLB")` |
| FBX | `bpy.ops.export_scene.fbx(filepath="out.fbx")` |
| USD | `bpy.ops.wm.usd_export(filepath="out.usdc")` |
| STL | `bpy.ops.wm.stl_export(filepath="out.stl")` |

Apply transforms before export:

```python
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
```
