"""
NeuroPaw — v6_render_set.py
Ключевые рендеры (по умолчанию 960×540): колено в крайних положениях, позы «лежит»
и «встаёт», голова в разрезе, нервная система. Файл не сохраняет.
Запуск: blender --background robodog_v6.blend --python scripts/v6_render_set.py -- [W H]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v6lib import checks, rig  # noqa: E402
from v6lib.layout import AXIS_Z, BASE, FOOT_R, LEGS, LL, N, UL, stand_pose  # noqa: E402

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
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.86, 0.87, 0.9, 1)
for name, rot, e in (("key", (45, 0, 35), 3.5), ("fill", (60, 0, 215), 1.2)):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'SUN'))
    l.data.energy = e
    l.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(l)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam


def shot(name, target, direction, span, ortho=True):
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    cam.data.ortho_scale = span
    cam.data.lens = 50
    t = Vector(target) * 0.001
    d = Vector(direction).normalized()
    cam.location = t + d * (1.5 if ortho else span * 2.2)
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_start, cam.data.clip_end = 0.005, 10
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


ALL = "all" in argv
if ALL:
    # 1. колено FL в крайних положениях (вид слева, бедро как в стойке)
    for k in (65, 128):
        legs(46.6, k)
        knee = ARM.matrix_world @ ARM.pose.bones[N[3]].head * 1000
        shot(f"v6_knee_{k}", knee + Vector((0, 0, 25)), (0, 1, 0), 0.19)
    # 2. позы
    legs(90, 128)
    shot("v6_poses_lie", (0, 0, 120), (1, -1.2, 0.7), 0.42, ortho=False)
    legs(75, 115)
    shot("v6_poses_standup", (0, 0, 140), (1, -1.2, 0.7), 0.42, ortho=False)

# 3. голова в разрезе: срез оболочки по y > 0, вид слева
legs(46.6, 88.4)
cut = bpy.data.objects.new("cutter", bpy.data.meshes.new("cutter"))
import bmesh  # noqa: E402
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bm.to_mesh(cut.data)
bm.free()
sc.collection.objects.link(cut)
cut.scale = (0.4, 0.2, 0.4)
cut.location = (0.15, 0.1 + 0.0005, 0.3)
cut.hide_render = True
for n in ("Head_shell", "Head_face", "Head_muzzle", "Neck_link", "Ear_L", "Jaw"):
    o = bpy.data.objects[n]
    m = o.modifiers.new("cut", 'BOOLEAN')
    m.operation, m.object, m.solver = 'DIFFERENCE', cut, 'EXACT'
HIDE_L = ("Servo_19_ear_L", "Eye_L_GC9A01", "Mic_INMP441_L", "Jaw_lips_TPU")
for n in HIDE_L:
    bpy.data.objects[n].hide_render = True
bpy.context.view_layer.update()
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.18, 0.18, 0.19, 1)
head = ARM.matrix_world @ ARM.pose.bones[N[17]].head * 1000
shot("v6_head_cutaway", head + Vector((25, 0, 25)), (0.25, 1, 0.25), 0.2)
for n in ("Head_shell", "Head_face", "Head_muzzle", "Neck_link", "Ear_L", "Jaw"):
    o = bpy.data.objects[n]
    o.modifiers.remove(o.modifiers["cut"])
for n in HIDE_L:
    bpy.data.objects[n].hide_render = False

# 3б. задняя секция сверху без крышки: полка, PCA9685, «Тело», CAN, питание
bpy.data.objects["Body_rear_lid"].hide_render = True
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.18, 0.18, 0.19, 1)
shot("v6_rear_top", (-78, 0, 185), (0.12, -0.25, 1), 0.3)
bpy.data.objects["Body_rear_lid"].hide_render = False

# 4. нервная система: оболочка прозрачная, сервы по управляющей плате
ghost = bpy.data.materials.new("ghost")
ghost.use_nodes = True
bsdf = ghost.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.8, 0.82, 0.85, 1)
bsdf.inputs["Alpha"].default_value = 0.07
ghost.surface_render_method = 'BLENDED'


def emit(name, rgb, s=2.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Emission Color"].default_value = (*rgb, 1)
    b.inputs["Emission Strength"].default_value = s
    return m


BOARD = {"ESP32_Body": emit("brd_body", (0.0, 0.78, 0.85), 1.5),
         "ESP32_Senses": emit("brd_senses", (0.6, 0.2, 1.0), 1.5)}
BOARD_OBJ = {"ESP32_Body": "ESP32_Body", "ESP32_Senses": "ESP32_Senses",
             "ESP32_Brain": "ESP32_Brain", "ESP32_Comms": "ESP32_Comms"}
BCOL = {"ESP32_Body": (0.0, 0.78, 0.85), "ESP32_Senses": (0.6, 0.2, 1.0),
        "ESP32_Brain": (0.1, 0.9, 0.4), "ESP32_Comms": (0.1, 0.6, 1.0)}


def override(o, m):
    for s in o.material_slots:
        s.link = 'OBJECT'
        s.material = m


for c in ("Shell", "Structure"):
    for o in bpy.data.collections[c].all_objects:
        override(o, ghost)
for o in bpy.data.collections["Hardware"].all_objects:
    o.hide_render = True
for o in bpy.data.objects:
    if "servo_no" in o:
        override(o, BOARD[o["board"]])
for b, n in BOARD_OBJ.items():
    override(bpy.data.objects[n], emit(f"b_{b}", BCOL[b], 4.0))
override(bpy.data.objects["CAN_bus_cable"], emit("can_e", (1.0, 0.9, 0.1), 5.0))
override(bpy.data.objects["Power_head_harness"], emit("pwr_e", (0.9, 0.05, 0.05), 3.0))
override(bpy.data.objects["Sensor_I2C_sonar_cable"], emit("sig_e", (0.2, 0.5, 1.0), 3.0))
for n in ("Sonar_HCSR04", "IMU_front_MPU6050_0x69", "IMU_rear_MPU6050_0x68", "PCA9685_Body"):
    override(bpy.data.objects[n], emit(f"s_{n}", BCOL["ESP32_Body"], 1.2))
for n in ("Eye_L_GC9A01", "Eye_R_GC9A01", "Mic_INMP441_L", "Mic_INMP441_R", "INA226_jaw", "Amp_MAX98357A",
          "Speaker_35x25"):
    override(bpy.data.objects[n], emit(f"s_{n}", BCOL["ESP32_Senses"], 1.2))
for n in ("Camera_OV2640", "USB_flash_50GB", "OTG_socket_USB_A"):
    override(bpy.data.objects[n], emit(f"s_{n}", BCOL["ESP32_Brain"], 1.2))
sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.03, 0.03, 0.04, 1)
bpy.data.objects["Floor"].hide_render = True
shot("v6_nervous_system", (20, 0, 230), (0.9, -1.1, 0.9), 0.5, ortho=False)
