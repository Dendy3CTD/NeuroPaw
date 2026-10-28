"""Проверки модели: пересечения (BVH), стопы, тяги, угол передачи колена."""
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import rig
from .layout import BETA, KAPPA, KL, KNEE_U, LEGS, R1, R2, ROD_L

MM = 0.001
# касания по конструкции внутри одного звена или через ось
LEG_CONTACT = {("knee_horn", "thigh"), ("knee_lever", "thigh"),
               ("knee_horn", "knee_rod"), ("knee_lever", "knee_rod")}
# вал сервы проходит сквозь стенку; детали с props["mounted_on"] касаются опоры по конструкции
SHAFT_THROUGH = {"Servo_19_ear_L": "Head_shell", "Servo_20_ear_R": "Head_shell"}


def _trees():
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for name, link in rig.LINK.items():
        if link == "CABLE":
            continue
        o = bpy.data.objects[name]
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        out[name] = BVHTree.FromPolygons([mw @ v.co for v in me.vertices],
                                         [p.vertices[:] for p in me.polygons])
        ev.to_mesh_clear()
    return out


def _allowed(a, b):
    oa, ob = bpy.data.objects[a], bpy.data.objects[b]
    for s, o in ((oa, b), (ob, a)):
        drv = s.get("drives_bone", "")
        if drv and (drv == rig.LINK[o] or (drv.endswith("_knee")
                                            and rig.LINK[o] == f"MCH_{drv.split('_')[2]}_knee_horn")):
            return True     # вал сервы входит в качалку ведомого звена
        if s.get("bearing") and rig.LINK[o] in (rig.LINK[s.name], s.get("bearing_mate")):
            return True     # обойма в своём звене, ось ответного звена в отверстии
    if SHAFT_THROUGH.get(a) == b or SHAFT_THROUGH.get(b) == a:
        return True
    if a[:3] == b[:3] and a[:2] in LEGS:
        pair = tuple(sorted((a[3:], b[3:])))
        return pair in LEG_CONTACT
    return b in oa.get("mounted_on", ()) or a in ob.get("mounted_on", ())


def collisions():
    """Пересечения: разные звенья — все; одно звено — только электроника и сервы."""
    t = _trees()
    names = sorted(t)
    elec = {o.name for c in bpy.data.collections["Electronics"].children_recursive
            for o in c.objects}
    servos = {o.name for o in bpy.data.objects if "servo_no" in o}
    struct = {o.name for c in bpy.data.collections["Structure"].children_recursive for o in c.objects}
    hits = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            same = rig.LINK[a] == rig.LINK[b]
            if same and not ({a, b} & (elec | servos)):
                continue
            if same and not ({a, b} & elec) and {a, b} & struct:
                continue    # серва в своём кронштейне/ложементе — касание по конструкции
            if _allowed(a, b):
                continue
            if t[a].overlap(t[b]):
                hits.append((a, b))
    return hits


def feet():
    out = {}
    for leg, (xs, ys, n0) in LEGS.items():
        o = bpy.data.objects[f"{leg}_foot"]
        out[leg] = min((o.matrix_world @ v.co).z for v in o.data.vertices) / MM
    return out


def rods():
    out = {}
    for leg in LEGS:
        r = bpy.data.objects[f"{leg}_knee_rod"]
        out[leg] = r.matrix_world.to_scale().y
    return out


def transmission():
    """Мин. угол передачи (тяга ↔ рычаг) на ходе колена — по четырёхзвеннику."""
    pts = KL.evaluate(R1, R2, BETA, ROD_L, KNEE_U, KAPPA[0], KAPPA[1], 1.0)
    return min(p[2] for p in pts)


def bbox_mm():
    pts = [o.matrix_world @ v.co for name in rig.LINK
           if rig.LINK[name] != "CABLE" for o in [bpy.data.objects[name]]
           for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))) / MM
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))) / MM
    return lo, hi


def relink():
    """Восстановить rig.ARM и rig.LINK в загруженном .blend (вне build_v6)."""
    rig.ARM = bpy.data.objects["NeuroPaw_rig"]
    rig.LINK.clear()
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.name == "Floor":
            continue
        if any(m.type == 'ARMATURE' for m in o.modifiers):
            rig.LINK[o.name] = "CABLE"
        elif o.parent == rig.ARM and o.parent_type == 'BONE':
            rig.LINK[o.name] = o.parent_bone
