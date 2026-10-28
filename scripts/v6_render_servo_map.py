"""
NeuroPaw — v6_render_servo_map.py
Этап 2, рендеры: карта сервоприводов (слой Servo_map) — front, side, top, iso, back;
разнесённый вид (слой ViewLayer, без подписей). Файл не сохраняет.
Запуск: blender --background robodog_v6.blend --python scripts/v6_render_servo_map.py -- [W H]
→ renders/v6_servo_map_<вид>.png, renders/v6_exploded.png
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v6lib import checks, rig  # noqa: E402
from v6lib.layout import BASE, LEGS, N  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
W, H = (int(argv[0]), int(argv[1])) if len(argv) >= 2 else (960, 540)
OUT = os.path.join(BASE, "renders")
checks.relink()
ARM = rig.ARM
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.world = sc.world or bpy.data.worlds.new("w")
sc.world.use_nodes = True
for name, rot, e in (("key", (45, 0, 35), 3.5), ("fill", (60, 0, 215), 1.2), ("rim", (70, 0, 120), 1.0)):
    lt = bpy.data.objects.new(name, bpy.data.lights.new(name, 'SUN'))
    lt.data.energy = e
    lt.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(lt)
cam = bpy.data.objects["Cam_servo_map"]
sc.camera = cam


def legend_to_corner(s, right=False):
    root = bpy.data.objects["Legend"]
    k = 0.36
    root.scale = (s * k,) * 3
    x = s / 2 - s * k * 0.77 - s * 0.015 if right else -s / 2 + s * 0.015
    root.location = (x, s * 9 / 32 - s * 0.03, -0.2)


SUFFIXES = ("_leader", "_anchor", "_text", "_back")
SHOWN = {}                                         # подпись → на скольких видах видна


def declutter(view, pad=1.5):
    """Убираем наложения подписей в кадре: ближние к камере ставим первыми,
    подпись, чья подложка пересекает уже поставленную, на этом виде скрываем."""
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    items = []
    for o in bpy.data.collections["Labels"].all_objects:
        if o is None or not o.name.endswith("_back"):
            continue
        pts = [inv @ (o.matrix_world @ Vector(c)) * 1000 for c in o.bound_box]
        rect = (min(p.x for p in pts) - pad, max(p.x for p in pts) + pad,
                min(p.y for p in pts) - pad, max(p.y for p in pts) + pad)
        legend = o.name.startswith("Legend")         # легенда стоит всегда и ставится первой
        items.append((not legend, -max(p.z for p in pts), o.name[:-len("_back")], rect))
    kept, hidden = [], []
    for is_label, _, base, r in sorted(items):
        if not is_label:
            kept.append(r)
            continue
        hit = any(r[0] < k[1] and k[0] < r[1] and r[2] < k[3] and k[2] < r[3] for k in kept)
        (hidden if hit else kept).append(base if hit else r)
        if not hit:
            SHOWN[base] = SHOWN.get(base, 0) + 1
        for suffix in SUFFIXES:
            ob = bpy.data.objects.get(base + suffix)
            if ob:
                ob.hide_render = hit
    print(f"[render] {view}: подписей {len(kept) - sum(not i[0] for i in items)}, скрыто {len(hidden)}: {', '.join(sorted(hidden))}")


def shot(name, target, direction, span, right=False):
    cam.data.type, cam.data.ortho_scale = 'ORTHO', span
    t = Vector(target) * 0.001
    d = Vector(direction).normalized()
    cam.location = t + d * 2.0
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_start, cam.data.clip_end = 0.01, 10
    legend_to_corner(span, right)
    declutter(name)
    bpy.context.view_layer.update()
    sc.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("[render]", sc.render.filepath)


# ── карта сервоприводов: только слой Servo_map ────────────────────────────────
# в активном ViewLayer подписи исключены и не вычисляются — на время карты включаем,
# иначе declutter видит их все в нуле
LABELS_LC = bpy.context.view_layer.layer_collection.children["Labels"]
LABELS_LC.exclude = False
for vl in sc.view_layers:
    vl.use = vl.name == "Servo_map"
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.42, 0.44, 0.47, 1)
bpy.data.objects["Floor"].hide_render = True
VIEWS = [("front", (40, 0, 205), (1, 0, 0), 0.82), ("side", (-25, 0, 205), (0, 1, 0), 0.92),
         ("top", (-25, 0, 200), (0.0001, 0, 1), 0.92), ("iso", (0, 0, 190), (1, -1.15, 0.85), 0.95),
         ("back", (-40, 0, 205), (-1, 0, 0), 0.82)]
for v, tgt, d, span in VIEWS:
    shot(f"v6_servo_map_{v}", tgt, d, span, right=v == "side")
missing = sorted(o.name[:-len("_back")] for o in bpy.data.collections["Labels"].all_objects
                 if o is not None and o.name.endswith("_back") and not o.name.startswith("Legend") and not SHOWN.get(o.name[:-len("_back")]))
print("[render] подписи, не видные ни на одном виде:", missing or "нет")
for o in bpy.data.collections["Labels"].all_objects:
    if o is not None:
        o.hide_render = False
LABELS_LC.exclude = True

# ── разнесённый вид: слой ViewLayer (без подписей), узлы раздвинуты ───────────
for vl in sc.view_layers:
    vl.use = vl.name == "ViewLayer"
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.86, 0.87, 0.9, 1)


def subtree(b):
    return {b} | {c.name for c in ARM.data.bones[b].children_recursive}


GROUPS = [(subtree(N[17]), Vector((70, 0, 150))), (subtree(N[16]) - subtree(N[17]), Vector((45, 0, 75)))]
for leg, (xs, ys, n0) in LEGS.items():
    GROUPS.append((subtree(N[n0]), Vector((xs * 45, ys * 110, -15))))
GROUPS += [({N[15]}, Vector((-150, 0, 10))), ({N[13]}, Vector((75, 0, 0))), ({N[14]}, Vector((0, 0, 35))),
           ({"Root"}, Vector((-75, 0, 0)))]
moved = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name == "Floor" or o.parent != ARM:
        if any(m.type == 'ARMATURE' for m in o.modifiers):
            o.hide_render = True
        continue
    off = next((v for bones, v in GROUPS if o.parent_bone in bones), Vector())
    extra = Vector()
    cols = {c.name for c in o.users_collection}
    if o.name.endswith("_lid"):
        extra.z += 130
    elif cols & {"Body", "Comms", "Power", "Brain", "Senses"} and o.parent_bone in ("Root", N[13]):
        extra.z += 70
    if o.name in ("Chest_bridge", "Stern_bridge"):
        extra.x += 40 if o.name == "Chest_bridge" else -40
    if o.name == "Head_shell" or o.name == "Head_face":
        extra.z += 45
    moved.append((o, o.matrix_world.copy()))
    o.matrix_world = Matrix.Translation((off + extra) * 0.001) @ o.matrix_world
bpy.data.objects["Floor"].hide_render = True
cam.data.type = 'PERSP'
cam.data.lens = 50
t = Vector((0, 0, 0.23))
cam.location = t + Vector((1, -1.25, 0.8)).normalized() * 1.55
cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = os.path.join(OUT, "v6_exploded.png")
bpy.ops.render.render(write_still=True)
print("[render]", sc.render.filepath)
