"""
NeuroPaw — v6_poses.py
Позы на арматуре: пересечения (BVH), замыкание тяг, поле HC-SR04, упор колена; рендеры.
«Сидит»: задние ноги в нижнем положении, передние почти прямые, передняя секция поднята
позвоночником (14); наклон корпуса подбирается так, чтобы все четыре стопы стояли на полу.
Файл не сохраняет. Запуск:
blender --background robodog_v6.blend --python scripts/v6_poses.py -- [render]
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v6lib import checks, rig  # noqa: E402
from v6lib.layout import AXIS_Z, BASE, FOOT_R, KNEE_STOP, LEGS, LL, N, UL  # noqa: E402

RENDER = "render" in sys.argv
checks.relink()
ARM = rig.ARM
SONAR_HALF_DEG = 15.0          # HC-SR04: рабочий угол 15° → берём конус ±15° (с запасом)
FRONT_LEGS, REAR_LEGS = ("FL", "FR"), ("BL", "BR")


def leg_pose(theta, kappa):
    """Высота оси бедра над полом, если стопа на полу; (θ бедра, κ колена) в градусах."""
    t, p = math.radians(theta), math.radians(theta - kappa)
    return FOOT_R + UL * math.cos(t) + LL * math.cos(p)


def set_angles(front, rear, extra=None):
    angles = {}
    for leg, (xs, ys, n0) in LEGS.items():
        th, ka = front if leg in FRONT_LEGS else rear
        angles[N[n0 + 1]] = th
        angles[N[n0 + 2]] = -ka
    angles.update(extra or {})
    rig.pose(angles)


def feet_z(legs):
    return min(checks.feet()[lg] for lg in legs)


def put_on_floor(tilt):
    """Наклон всей модели вокруг Y (°, «−» — нос вверх) и посадка нижней стопы на Z = 0."""
    ARM.rotation_euler = (0, math.radians(tilt), 0)
    ARM.location.z = 0
    bpy.context.view_layer.update()
    ARM.location.z -= min(checks.feet().values()) * 0.001
    bpy.context.view_layer.update()


def solve_tilt():
    """Наклон, при котором передние и задние стопы на полу одновременно (секущие)."""
    def f(t):
        put_on_floor(t)
        return feet_z(FRONT_LEGS) - feet_z(REAR_LEGS)
    a, b = 0.0, -20.0
    fa, fb = f(a), f(b)
    for _ in range(25):
        if abs(fb) < 0.05 or fb == fa:
            break
        a, b, fa = b, b - fb * (b - a) / (fb - fa), fb
        fb = f(b)
    put_on_floor(b)
    return b


def pose(name, front, rear, extra=None, solve=False):
    set_angles(front, rear, extra)
    if solve:
        tilt = solve_tilt()
    else:
        ARM.rotation_euler = (0, 0, 0)
        ARM.location.z = (leg_pose(*rear) - AXIS_Z) * 0.001
        bpy.context.view_layer.update()
        tilt = 0.0
    return tilt


def hip_axis_z(legs):
    return sum((ARM.matrix_world @ ARM.data.bones[N[LEGS[lg][2] + 1]].head_local).z
               for lg in legs) / len(legs) * 1000


def sonar_field():
    """Лучи из обоих излучателей в конусе ±15°: ближайшее попадание в сам робот и в пол, мм."""
    s = bpy.data.objects["Sonar_HCSR04"]
    mw = s.matrix_world
    axis = (mw.to_3x3() @ Vector((1, 0, 0))).normalized()     # меш в осях мира: излучатели к +X
    side = (mw.to_3x3() @ Vector((0, 1, 0))).normalized()
    up = axis.cross(side)
    trees = checks._trees()
    skip = {"Sonar_HCSR04", "Body_front_end"}
    best, floor = (1e9, None), 1e9
    for tx in (-13, 13):
        o = mw @ (Vector((13.7, tx, 1)) * 0.001)
        for ring in (0.0, SONAR_HALF_DEG / 2, SONAR_HALF_DEG):
            for k in range(1 if ring == 0 else 16):
                ph = 2 * math.pi * k / 16
                r = math.radians(ring)
                d = (axis * math.cos(r) + (side * math.cos(ph) + up * math.sin(ph)) * math.sin(r)).normalized()
                for name, t in trees.items():
                    if name in skip:
                        continue
                    hit = t.ray_cast(o, d, 1.0)
                    if hit[0] is not None and hit[3] * 1000 < best[0]:
                        best = (hit[3] * 1000, name)
                if d.z < 0:
                    floor = min(floor, -o.z / d.z * 1000)
    return best, floor


POSES = [
    ("stand", (46.6, 88.4), (46.6, 88.4), None, False),
    ("stand_head_L90", (46.6, 88.4), (46.6, 88.4), {N[17]: 90.0}, False),
    ("stand_head_R90", (46.6, 88.4), (46.6, 88.4), {N[17]: -90.0}, False),
    ("standup_mid", (75.0, 115.0), (75.0, 115.0), None, False),
    ("lie", (90.0, 128.0), (90.0, 128.0), {N[17]: 0.0, N[16]: 10.0}, False),
    ("lie_head_L90", (90.0, 128.0), (90.0, 128.0), {N[17]: 90.0, N[16]: 10.0}, False),
    ("stand_tall", (30.0, 65.0), (30.0, 65.0), None, False),
]


def sit_pose():
    """Передние бедро/колено подбираем: нога ≈ вертикальна, стопа под плечом."""
    best = None
    for th in range(-10, 81, 5):
        set_angles((th, 70.0), (90.0, 128.0), {N[14]: SPINE_SIT, N[16]: -20.0})
        tilt = solve_tilt()
        hip = ARM.matrix_world @ ARM.data.bones[N[2]].head_local
        foot = bpy.data.objects["FL_foot"]
        fx = sum((foot.matrix_world @ v.co).x for v in foot.data.vertices) / len(foot.data.vertices)
        dev = abs(fx - hip.x) * 1000
        if best is None or dev < best[0]:
            best = (dev, th, tilt)
    return best


# знак наклона позвоночника, поднимающего переднюю секцию: пробуем ±20°
SPINE_SIT = 20.0
set_angles((46.6, 88.4), (46.6, 88.4), {N[14]: 20.0})
z_plus = (ARM.matrix_world @ ARM.data.bones[N[16]].head_local).z
set_angles((46.6, 88.4), (46.6, 88.4), {N[14]: -20.0})
if (ARM.matrix_world @ ARM.data.bones[N[16]].head_local).z > z_plus:
    SPINE_SIT = -20.0
dev, th_sit, _ = sit_pose()
POSES.insert(4, ("sit", (float(th_sit), 70.0), (90.0, 128.0), {N[14]: SPINE_SIT, N[16]: -20.0}, True))
POSES.insert(5, ("sit_head_R90", (float(th_sit), 70.0), (90.0, 128.0),
                 {N[14]: SPINE_SIT, N[16]: -20.0, N[17]: -90.0}, True))

out, summary = [], {}
for name, fr, re_, extra, solve in POSES:
    tilt = pose(name, fr, re_, extra, solve)
    hits = checks.collisions()
    feet = checks.feet()
    rods = checks.rods()
    (d_self, o_self), d_floor = sonar_field()
    belly = min((o.matrix_world @ v.co).z for o in bpy.data.objects
                if o.name.startswith("Body_") and o.type == 'MESH' for v in o.data.vertices) * 1000
    line = (f"[poses] {name}: перед {fr[0]:.0f}/{fr[1]:.0f}°, зад {re_[0]:.0f}/{re_[1]:.0f}°, "
            f"наклон {-tilt:+.1f}°, оси бёдер П {hip_axis_z(FRONT_LEGS):.0f} / З {hip_axis_z(REAR_LEGS):.0f} мм, "
            f"живот {belly:.0f} мм, стопы {min(feet.values()):.1f}…{max(feet.values()):.1f}, "
            f"тяги {min(rods.values()):.3f}…{max(rods.values()):.3f}, пересечений {len(hits)}; "
            f"HC-SR04: себя {'нет' if o_self is None else f'{d_self:.0f} мм ({o_self})'}, пол {d_floor:.0f} мм")
    print(line)
    for a, b in hits:
        print(f"         {a} × {b}")
    out.append(line)
    summary[name] = {"hits": len(hits), "tilt_deg": -tilt, "sonar_self_mm": None if o_self is None else d_self,
                     "sonar_self_obj": o_self, "sonar_floor_mm": d_floor, "belly_mm": belly,
                     "hip_front_mm": hip_axis_z(FRONT_LEGS), "hip_rear_mm": hip_axis_z(REAR_LEGS)}
    if RENDER and name in ("sit",):
        sys.argv = [sys.argv[0], "--", f"v6_poses_{name}"]
        exec(open(os.path.join(HERE, "render_views.py")).read(), {"__file__": os.path.join(HERE, "render_views.py")})
print(f"[poses] «сидит»: передние бедро {th_sit}°, колено 70°, стопа от плеча по X {dev:.0f} мм, "
      f"позвоночник {SPINE_SIT:+.0f}°")

# упор колена: до упора — без касания, за упором — голень упирается в бедро
ARM.rotation_euler = (0, 0, 0)
for c in [c for pb in ARM.pose.bones for c in pb.constraints if c.type == 'LIMIT_ROTATION']:
    c.mute = True
stop = {}
for ka in (65, 128.0, KNEE_STOP - 0.2, KNEE_STOP + 0.8, 130.0):
    set_angles((46.6, ka), (46.6, ka))
    ARM.location.z = 0
    bpy.context.view_layer.update()
    hits = [h for h in checks.collisions() if h[0].startswith("FL_") and h[1].startswith("FL_")]
    stop[ka] = [f"{a} × {b}" for a, b in hits]
    print(f"[poses] колено κ={ka}°: тяга FL {checks.rods()['FL']:.3f}, касания в FL: {stop[ka] or 'нет'}")
summary["knee_stop"] = {str(k): v for k, v in stop.items()}
summary["sit"]["front_hip_deg"] = th_sit
summary["sit"]["spine_deg"] = SPINE_SIT
json.dump(summary, open(os.path.join(BASE, "docs", "poses_v6.json"), "w"), ensure_ascii=False, indent=1)
