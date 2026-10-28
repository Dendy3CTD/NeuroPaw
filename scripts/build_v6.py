"""
NeuroPaw — build_v6.py
Этап 1 (v6): 20 сервоприводов, корпус из двух секций с позвоночником,
шея, голова с челюстью, уши, хвост, нервная система 4 × ESP32-S3 + CAN.
Геометрия и раскладка — scripts/v6lib/, параметры — params.json.
Запуск: blender --background --python scripts/build_v6.py
Результат: robodog_v6.blend (старые robodog_v*.blend не трогает)
"""
import os
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
bpy.ops.wm.read_factory_settings(use_empty=True)   # до импорта: материалы создаются при импорте

from v6lib import checks, rig  # noqa: E402
from v6lib.cable import tube  # noqa: E402
from v6lib.geom import Mesh, col, mat  # noqa: E402
from v6lib.layout import BASE, LEGS, N, SERVOS, STAND_HIP, STAND_KNEE, bones, stand_pose  # noqa: E402
from v6lib.parts import M  # noqa: E402
from v6lib.parts_body import (build_body, build_boards, build_bridges, build_electronics,  # noqa: E402
                              build_power_panel, build_spine, build_tail, build_tray)
from v6lib.parts_head import build_head, build_neck  # noqa: E402
from v6lib.parts_leg import build_leg  # noqa: E402

OUT = os.path.join(BASE, "robodog_v6.blend")
SIMPLE = None
H, NK, FRONT, SP, ROOT = N[17], N[16], N[13], N[14], "Root"
# CAN: Органы чувств (120 Ом) — Мозг — [шея, левая сторона] — Связь — [позвоночник] — Тело (120 Ом)
CAN_ROUTE = [
    (128, 10, 294.5, H), (134, 22, 295, H), (128, 27, 294.5, H), (138, 36, 293, H),
    (124, 33, 284, H), (122, 32, 270, NK), (121, 32, 250, NK), (120, 32, 234, NK),
    (117, 32, 224, FRONT), (100, 26, 214, FRONT), (70, 18, 213, FRONT), (52, 17.5, 213.5, FRONT),
    (40, 40, 206, FRONT), (24, 46, 200, FRONT), (-2, 46, 194, SP), (-29, 46, 191, ROOT),
    (-45, 46, 186, ROOT), (-56, 43.5, 183, ROOT),
]
# питание головы (6 В серв + 5 В логики): UBEC-П/DC-DC → правая сторона, петля за осью наклона шеи
POWER_HEAD_ROUTE = [
    (84, -20, 168, FRONT), (100, -30, 190, FRONT), (110, -33, 214, FRONT), (108, -33, 226, FRONT),
    (107, -33, 234, NK), (110, -33, 252, NK), (114, -33, 272, NK), (124, -30, 286, H),
    (140, -32, 293, H), (150, -36, 296, H),
]
# I2C переднего IMU и HC-SR04 (Trig/Echo) — витая пара по левому борту через позвоночник к «Телу»
SENSOR_ROUTE = [
    (121, 12, 186, FRONT), (110, 30, 180, FRONT), (70, 40, 160, FRONT), (58, 0, 157, FRONT),
    (40, 42, 170, FRONT), (20, 44, 190, FRONT), (-2, 44, 196, SP), (-29, 44, 197, ROOT),
    (-45, 30, 196, ROOT), (-57, 14, 195, ROOT),
]
# шлейф камеры (штатный ~21 мм), гибкий OTG 10 см, запасной провод 5 В от DC-DC к гнезду флешки
CAM_FPC_ROUTE = [(164.8, 2.5, 336, H), (171, 1.5, 335, H), (176.5, 0, 334.5, H)]
OTG_ROUTE = [(169, -36, 341.5, H), (172, -22, 333, H), (172, -2, 324, H), (169, 10, 318, H),
             (166.5, 12.5, 316, H)]
OTG_5V_ROUTE = [(150, -36, 296, H), (156, -26, 306, H), (164, -8, 311, H), (166.5, 11.5, 312.5, H)]


def build():
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    rig.build("NeuroPaw_rig", bones(), col("Rig"))
    build_body()
    build_spine()
    build_tail()
    build_power_panel()
    build_bridges()
    build_tray()
    build_electronics()
    build_boards()
    build_neck()
    build_head()
    global SIMPLE
    SIMPLE = all([build_leg(leg) for leg in LEGS])
    tube("CAN_bus_cable", CAN_ROUTE, 1.6, M["can"], col("Electronics/CAN"))
    tube("Power_head_harness", POWER_HEAD_ROUTE, 2.2, mat("Power_cable", (0.6, 0.05, 0.03), 0.5),
         col("Electronics/Power"))
    tube("Sensor_I2C_sonar_cable", SENSOR_ROUTE, 1.2, mat("Signal_cable", (0.1, 0.3, 0.8), 0.5),
         col("Electronics/Body"))
    tube("Camera_FPC_21mm", CAM_FPC_ROUTE, 0.6, M["gold"], col("Electronics/Brain"))
    tube("OTG_cable_10cm", OTG_ROUTE, 1.8, M["dark"], col("Electronics/Brain"))
    tube("OTG_5V_backup_wire", OTG_5V_ROUTE, 0.7, mat("Power_cable", (0.6, 0.05, 0.03), 0.5),
         col("Electronics/Power"))
    for no, name, joint, kind, rr, *_ in SERVOS:
        rig.limit(name, *rr)
    floor = Mesh().mat(mat("Floor", (0.55, 0.56, 0.58), 0.8)).box((-600, 600), (-600, 600), (-2, 0))
    floor.bm.transform(Matrix.Scale(0.001, 4))
    me = bpy.data.meshes.new("Floor")
    floor.bm.to_mesh(me)
    floor.bm.free()
    me.materials.append(floor.mats[0])
    fo = bpy.data.objects.new("Floor", me)
    scene.collection.objects.link(fo)


def report():
    print(f"[v6] сервоприводов: {sum(1 for o in bpy.data.objects if 'servo_no' in o)} "
          f"(в таблице {len(SERVOS)})")
    for c in ("MG996R", "DS3235MG", "MG90S", "SG90"):
        print(f"[v6]   {c}: {len(bpy.data.collections[c].objects)}")
    print(f"[v6] кости: {len(rig.ARM.data.bones)}; стойка: бедро {STAND_HIP:.1f}°, "
          f"колено {STAND_KNEE:.1f}°")
    print(f"[v6] угол передачи колена на ходе 65…130°: мин {checks.transmission():.1f}°")
    print(f"[v6] драйверы качалок — простые выражения: {SIMPLE}")
    print(f"[v6] подшипников: {sum(1 for o in bpy.data.objects if o.get('bearing'))}")
    for leg, z in checks.feet().items():
        print(f"[v6] стопа {leg}: низ Z = {z:.2f} мм")
    print("[v6] тяги (масштаб, 1.000 = длина не меняется): "
          + ", ".join(f"{k} {v:.3f}" for k, v in checks.rods().items()))
    hits = checks.collisions()
    print(f"[v6] пересечений: {len(hits)}")
    for a, b in hits:
        print(f"      {a}  ×  {b}")
    lo, hi = checks.bbox_mm()
    print(f"[v6] габарит: {hi.x - lo.x:.0f} × {hi.y - lo.y:.0f} × {hi.z - lo.z:.0f} мм "
          f"(X {lo.x:.0f}…{hi.x:.0f}, Z {lo.z:.1f}…{hi.z:.0f})")


build()
rig.pose(stand_pose())
report()
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"[v6] сохранено: {OUT}")
