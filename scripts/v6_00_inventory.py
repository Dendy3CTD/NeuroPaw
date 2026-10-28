"""
NeuroPaw — v6_00_inventory.py
Этап 0 (v6): инвентаризация сцены. Только чтение, файл не сохраняется.
Запуск: blender --background robodog_v3.blend --python scripts/v6_00_inventory.py
"""
import math
from collections import Counter

import bpy
from mathutils import Vector


def world_dims_mm(obj):
    """Габарит по вершинам в мировых координатах (bound_box у повёрнутых раздут)."""
    if obj.type != 'MESH' or not obj.data.vertices:
        return "-"
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    d = [(max(p[i] for p in pts) - min(p[i] for p in pts)) * 1000 for i in range(3)]
    return "×".join(f"{x:.1f}" for x in d)


scene = bpy.context.scene
us = scene.unit_settings
print(f"\n=== SCENE units={us.system}/{us.length_unit} scale={us.scale_length} "
      f"engine={scene.render.engine} camera={scene.camera}")
print(f"objects={len(bpy.data.objects)} materials={len(bpy.data.materials)} "
      f"armatures={len(bpy.data.armatures)} view_layers={[v.name for v in scene.view_layers]}")
print("types:", dict(Counter(o.type for o in bpy.data.objects)))
print("collections:", [(c.name, len(c.objects)) for c in bpy.data.collections])

print("\n=== OBJECTS (мировой габарит X×Y×Z, мм)")
for o in sorted(bpy.data.objects, key=lambda o: (o.users_collection[0].name, o.name)):
    col = ",".join(c.name for c in o.users_collection)
    polys = len(o.data.polygons) if o.type == 'MESH' else "-"
    mats = sorted({s.material.name for s in o.material_slots if s.material})
    mods = [m.type for m in o.modifiers]
    cons = [c.type for c in o.constraints]
    print(f"{o.name:<24} {col:<12} {o.type:<6} {world_dims_mm(o):<20} "
          f"parent={o.parent.name if o.parent else '-':<18} polys={polys:<5} "
          f"mats={mats} mods={mods} cons={cons}")

print("\n=== JOINTS (пустышки с ненулевым поворотом)")
for o in bpy.data.objects:
    if o.type == 'EMPTY' and any(abs(a) > 1e-6 for a in o.rotation_euler):
        print(f"{o.name:<18} rot={[round(math.degrees(a), 1) for a in o.rotation_euler]} "
              f"limits={[c.type for c in o.constraints if c.type.startswith('LIMIT')]}")

print("\n=== ARMATURES")
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
if not arms:
    print("нет")
for a in arms:
    for b in a.data.bones:
        print(f"{a.name}/{b.name} parent={b.parent.name if b.parent else '-'}")

print("\n=== MATERIALS")
for m in bpy.data.materials:
    b = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
    if b:
        c = b.inputs["Base Color"].default_value
        print(f"{m.name:<16} color=({c[0]:.2f},{c[1]:.2f},{c[2]:.2f}) "
              f"rough={b.inputs['Roughness'].default_value:.2f} "
              f"metal={b.inputs['Metallic'].default_value:.1f} users={m.users}")
print("\n=== DONE")
