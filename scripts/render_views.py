"""
NeuroPaw — render_views.py
Рендерит 4 вида (front, side, top, iso) в renders/<prefix>_<view>.png.
Сцену НЕ сохраняет: временные камера/свет удаляются только из памяти.
Запуск: blender --background <file>.blend --python scripts/render_views.py -- <prefix>
"""
import bpy
import math
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREFIX = argv[0] if argv else "view"
SHOW_HELPERS = "--helpers" in argv   # показывать Labels/Axes

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "renders")
os.makedirs(OUT, exist_ok=True)

scene = bpy.context.scene

# Вспомогательные коллекции прячем из рендера, если не просили
for name in ("Labels", "Axes"):
    col = bpy.data.collections.get(name)
    if col:
        col.hide_render = not SHOW_HELPERS

# Габариты модели (без пола и вспомогательных объектов)
pts = []
for o in scene.objects:
    if o.type != 'MESH' or o.hide_render or o.name.startswith("Floor"):
        continue
    if any(c.hide_render for c in o.users_collection):
        continue
    pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center = (lo + hi) / 2
size = hi - lo
print(f"[render] bbox mm: lo={tuple(round(v*1000) for v in lo)} hi={tuple(round(v*1000) for v in hi)}")

# Временный свет, если в сцене его нет
temp = []
if not any(o.type == 'LIGHT' for o in scene.objects):
    for name, typ, loc, energy, rot in [
        ("tmp_key", 'SUN', (1, -1, 2), 3.5, (math.radians(45), 0, math.radians(35))),
        ("tmp_fill", 'SUN', (-1, 1, 1), 1.2, (math.radians(60), 0, math.radians(215))),
    ]:
        ld = bpy.data.lights.new(name, typ)
        ld.energy = energy
        lo_ = bpy.data.objects.new(name, ld)
        lo_.location = loc
        lo_.rotation_euler = rot
        scene.collection.objects.link(lo_)
        temp.append(lo_)

if scene.world is None:
    scene.world = bpy.data.worlds.new("tmp_world")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.86, 0.87, 0.90, 1)
    bg.inputs["Strength"].default_value = 0.9

cam_data = bpy.data.cameras.new("tmp_cam")
cam = bpy.data.objects.new("tmp_cam", cam_data)
scene.collection.objects.link(cam)
temp.append(cam)
scene.camera = cam

scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False
aspect = scene.render.resolution_x / scene.render.resolution_y


def look_at(obj, target):
    d = (Vector(target) - obj.location)
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def ortho_view(name, direction, span_w, span_h):
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = max(span_w, span_h * aspect) * 1.15
    cam.location = center + Vector(direction).normalized() * 2.0
    look_at(cam, center)
    if direction == (0, 0, 1):
        cam.rotation_euler = (0, 0, 0)
    render(name)


def render(name):
    cam_data.clip_start = 0.01
    cam_data.clip_end = 10
    scene.render.filepath = os.path.join(OUT, f"{PREFIX}_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"[render] {scene.render.filepath}")


ortho_view("front", (1, 0, 0), size.y, size.z)
ortho_view("side", (0, -1, 0), size.x, size.z)
ortho_view("top", (0, 0, 1), size.x, size.y)

cam_data.type = 'PERSP'
cam_data.lens = 50
diag = size.length
cam.location = center + Vector((1.0, -1.1, 0.75)).normalized() * diag * 2.3
look_at(cam, center)
render("iso")

for o in temp:
    bpy.data.objects.remove(o, do_unlink=True)
