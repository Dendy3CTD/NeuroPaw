"""Кабели как меш-трубки, деформируемые арматурой.

Каждая контрольная точка привязана к кости; между точками разных костей вес
смешивается линейно, поэтому петля через сустав гнётся вместе с позой.
"""
import bmesh
import bpy
from mathutils import Vector

from . import rig
from .geom import MM


def _catmull(pts, n):
    out = []
    p = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out


def tube(name, points, radius, material, collection, seg=8, sub=6):
    """points: [(x, y, z, кость)] в мм."""
    pts = [Vector(p[:3]) for p in points]
    bones = [p[3] for p in points]
    path = _catmull(pts, sub)
    # для каждой точки пути — пара (кость, вес) по ближайшим контрольным точкам
    weights = []
    for i in range(len(path)):
        f = i / sub
        a = min(int(f), len(pts) - 1)
        b = min(a + 1, len(pts) - 1)
        t = f - int(f) if a != b else 0.0
        weights.append(((bones[a], 1 - t), (bones[b], t)))

    bm = bmesh.new()
    rings = []
    prev_n = None
    for i, c in enumerate(path):
        d = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        n = prev_n if prev_n is not None else d.orthogonal().normalized()
        n = (n - d * n.dot(d)).normalized()
        prev_n = n
        bnorm = d.cross(n)
        ring = []
        for k in range(seg):
            import math
            a = 2 * math.pi * k / seg
            ring.append(bm.verts.new((c + (n * math.cos(a) + bnorm * math.sin(a)) * radius) * MM))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    collection.objects.link(o)

    groups = {}
    for i, wl in enumerate(weights):
        for bone, w in wl:
            if w <= 0:
                continue
            if bone not in groups:
                groups[bone] = o.vertex_groups.new(name=bone)
            groups[bone].add(list(range(i * seg, (i + 1) * seg)), w, 'ADD')
    o.parent = rig.ARM
    mod = o.modifiers.new("Armature", 'ARMATURE')
    mod.object = rig.ARM
    rig.LINK[name] = "CABLE"
    return o
