"""
NeuroPaw — 01_analyze_scene.py
Этап 1: инвентаризация сцены (только чтение, файл не сохраняется).
Запуск: blender --background robodog_v2.blend --python scripts/01_analyze_scene.py
"""
import bpy
from mathutils import Vector


def fmt(v, k=1000.0, nd=1):
    return "(" + ", ".join(f"{x * k:.{nd}f}" for x in v) + ")"


def world_bbox(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


scene = bpy.context.scene
us = scene.unit_settings
print(f"\n=== SCENE '{scene.name}' units={us.system} scale_length={us.scale_length} "
      f"length_unit={us.length_unit} engine={scene.render.engine}")
print(f"objects={len(bpy.data.objects)} meshes={len(bpy.data.meshes)} "
      f"materials={len(bpy.data.materials)} armatures={len(bpy.data.armatures)}")
print("collections:", [(c.name, len(c.objects)) for c in bpy.data.collections])

print("\n=== OBJECTS (мм; rot в градусах)")
for obj in sorted(bpy.data.objects, key=lambda o: (o.users_collection[0].name if o.users_collection else "", o.name)):
    col = ",".join(c.name for c in obj.users_collection)
    lo, hi = world_bbox(obj)
    rot = [round(a * 57.29578, 1) for a in obj.rotation_euler]
    scale = tuple(round(s, 4) for s in obj.scale)
    polys = len(obj.data.polygons) if obj.type == 'MESH' else "-"
    mats = [s.material.name if s.material else None for s in obj.material_slots]
    mods = [f"{m.type}:{m.name}" for m in obj.modifiers]
    print(f"{obj.name:<22} col={col:<12} type={obj.type:<7} dims={fmt(obj.dimensions)} "
          f"loc={fmt(obj.location)} rot={rot} scale={scale} parent={obj.parent.name if obj.parent else None} "
          f"polys={polys} mats={mats} mods={mods} wbbox_z=[{lo.z*1000:.1f},{hi.z*1000:.1f}]")
    if obj.type == 'FONT':
        print(f"    text='{obj.data.body}'")

print("\n=== ELECTRONICS")
col = bpy.data.collections.get("Electronics")
if col:
    for o in col.objects:
        lo, hi = world_bbox(o)
        print(f"{o.name:<12} size={fmt(o.dimensions)} min={fmt(lo)} max={fmt(hi)}")

print("\n=== LEG JOINT CONNECTIVITY (зазоры между соседними звеньями)")
def gap(a, b):
    """Минимальный зазор между AABB двух объектов (0 = пересекаются/касаются)."""
    la, ha = world_bbox(a); lb, hb = world_bbox(b)
    d = [max(lb[i] - ha[i], la[i] - hb[i], 0) for i in range(3)]
    return Vector(d).length * 1000

chain = ["sh_servo", "bracket", "hip_servo", "thigh", "kn_servo", "shin", "foot"]
for tag in ("FL", "FR", "RL", "RR"):
    objs = [bpy.data.objects.get(f"{tag}_{n}") for n in chain]
    parts = []
    for a, b in zip(objs, objs[1:]):
        if a and b:
            parts.append(f"{a.name.split('_',1)[1]}→{b.name.split('_',1)[1]}={gap(a, b):.1f}")
    foot = bpy.data.objects.get(f"{tag}_foot")
    fz = world_bbox(foot)[0].z * 1000 if foot else float('nan')
    print(f"{tag}: " + "  ".join(parts) + f"  foot_min_z={fz:.1f}mm")

body = bpy.data.objects.get("Body_main")
if body:
    print("\n=== BODY vs SERVOS (AABB overlap)")
    lb, hb = world_bbox(body)
    for o in bpy.data.objects:
        if o.type == 'MESH' and "servo" in o.name:
            lo, hi = world_bbox(o)
            ov = all(lo[i] < hb[i] and hi[i] > lb[i] for i in range(3))
            if ov:
                print(f"  {o.name} пересекается с корпусом")
print("\n=== DONE")
