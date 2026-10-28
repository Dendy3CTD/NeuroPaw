"""
NeuroPaw — v6_render_readme.py
Картинки для README (по умолчанию 1280×720, слой ViewLayer без подписей):
полная собака (вид 3/4 и сбоку), «версия 2» — без головы, шеи и хвоста, поза «лежит».
Файл не сохраняет.
Запуск: blender --background robodog_v6.blend --python scripts/v6_render_readme.py -- [W H]
→ renders/readme_*.png
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v6lib import checks, rig  # noqa: E402
from v6lib.layout import AXIS_Z, BASE, FOOT_R, LEGS, LL, N, UL  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
W, H = (int(argv[0]), int(argv[1])) if len(argv) >= 2 else (1280, 720)
OUT = os.path.join(BASE, "renders")
checks.relink()
ARM = rig.ARM
sc = bpy.context.scene
for vl in sc.view_layers:
    vl.use = vl.name == "ViewLayer"
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.world = sc.world or bpy.data.worlds.new("w")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.86, 0.87, 0.9, 1)
for name, rot, e in (("key", (45, 0, 35), 3.5), ("fill", (60, 0, 215), 1.2), ("rim", (70, 0, 120), 0.8)):
    lt = bpy.data.objects.new(name, bpy.data.lights.new(name, 'SUN'))
    lt.data.energy = e
    lt.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(lt)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam


def shot(name, target, direction, dist):
    cam.data.type, cam.data.lens = 'PERSP', 50
    t = Vector(target) * 0.001
    cam.location = t + Vector(direction).normalized() * dist
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_start, cam.data.clip_end = 0.005, 20
    sc.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("[render]", sc.render.filepath)


def legs(theta, kappa):
    a = {}
    for leg, (xs, ys, n0) in LEGS.items():
        a[N[n0 + 1]], a[N[n0 + 2]] = theta, -kappa
    rig.pose(a)
    t, p = math.radians(theta), math.radians(theta - kappa)
    ARM.location.z = (FOOT_R + UL * math.cos(t) + LL * math.cos(p) - AXIS_Z) * 0.001
    bpy.context.view_layer.update()


def head_and_tail():
    """Объекты на костях шеи/головы (16→) и хвоста (15) — в версии 2 их ещё нет."""
    bones = {N[16], N[15]} | {c.name for c in ARM.data.bones[N[16]].children_recursive}
    return [o for o in bpy.data.objects
            if o.parent == ARM and o.parent_bone in bones
            or o.name.startswith(("Servo_15", "Servo_16"))
            or o.name in ("Power_head_harness", "OTG_5V_backup_wire", "OTG_cable_10cm",
                           "CAN_bus_cable")]


ISO = (1, -1.25, 0.75)
legs(46.6, 88.4)                                   # стойка
shot("readme_v3_full", (0, 0, 200), ISO, 1.35)
shot("readme_side", (0, 0, 200), (0, -1, 0.08), 1.45)
hidden = head_and_tail()
for o in hidden:
    o.hide_render = True
shot("readme_v2_body", (0, 0, 180), ISO, 1.3)
for o in hidden:
    o.hide_render = False
legs(90, 128)                                      # лежит
shot("readme_v4_lie", (0, 0, 130), ISO, 1.3)
