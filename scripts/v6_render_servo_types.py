"""
NeuroPaw — v6_render_servo_types.py
Крупный план трёх типов сервоприводов (MG996R / MG90S / SG90) рядом.
Сцену не сохраняет. Запуск:
blender --background robodog_v6.blend --python scripts/v6_render_servo_types.py
→ renders/v6_servo_types.png
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scene = bpy.context.scene
for o in scene.objects:
    o.hide_render = True

SHOW = [("Servo_03_FL_knee", -0.045), ("Servo_16_neck_yaw", 0.0), ("Servo_17_jaw", 0.035)]
for name, x in SHOW:
    src = bpy.data.objects[name]
    o = bpy.data.objects.new(name + "_view", src.data)
    o.matrix_world = Matrix.Translation((x, 0, 0.2)) @ Matrix.Rotation(math.radians(-30), 4, 'Z')
    # вал вверх: исходная серва уже повёрнута, берём меш в её локальной системе вала
    scene.collection.objects.link(o)

sun = bpy.data.objects.new("tmp_sun", bpy.data.lights.new("tmp_sun", 'SUN'))
sun.data.energy = 4
sun.rotation_euler = (math.radians(40), 0, math.radians(30))
scene.collection.objects.link(sun)
cam = bpy.data.objects.new("tmp_cam", bpy.data.cameras.new("tmp_cam"))
cam.data.lens = 85
cam.location = Vector((0.06, -0.33, 0.33))
cam.rotation_euler = (Vector((-0.005, 0, 0.19)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.resolution_x, scene.render.resolution_y = 1400, 800
scene.render.filepath = os.path.join(BASE, "renders", "v6_servo_types.png")
bpy.ops.render.render(write_still=True)
print("[servo_types]", scene.render.filepath)
