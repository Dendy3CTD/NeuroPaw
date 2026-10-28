"""Геометрические примитивы v6: всё в мм в мировых координатах позы покоя."""
import bmesh
import bpy
from mathutils import Matrix, Vector

MM = 0.001


def frame(origin, z_axis, x_axis):
    """Матрица локальной системы: начало, ось Z, ось X (Y = Z × X)."""
    z = Vector(z_axis).normalized()
    x = Vector(x_axis).normalized()
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def rng(a, b, s=1):
    return tuple(sorted((a * s, b * s)))


class Mesh:
    """bmesh-сборщик: каждый примитив получает текущий материал."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []
        self.cur = 0

    def mat(self, m):
        if m not in self.mats:
            self.mats.append(m)
        self.cur = self.mats.index(m)
        return self

    def _tag(self, before):
        """Новые грани = которых не было до примитива (индексы bmesh переиспользуются)."""
        for f in self.bm.faces:
            if f not in before:
                f.material_index = self.cur

    def box(self, x, y, z, m=None):
        n0 = set(self.bm.faces)
        c = Vector(((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2))
        s = Matrix.Diagonal((x[1] - x[0], y[1] - y[0], z[1] - z[0], 1))
        bmesh.ops.create_cube(self.bm, size=1.0,
                              matrix=(m or Matrix()) @ Matrix.Translation(c) @ s)
        self._tag(n0)
        return self

    def cyl(self, center, axis, r, h, seg=32, m=None, r2=None):
        n0 = set(self.bm.faces)
        rot = Vector((0, 0, 1)).rotation_difference(Vector(axis)).to_matrix().to_4x4()
        mat = (m or Matrix()) @ Matrix.Translation(Vector(center)) @ rot
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=r, radius2=r if r2 is None else r2, depth=h, matrix=mat)
        self._tag(n0)
        return self

    def ring(self, center, axis, r_out, r_in, h, seg=40, m=None):
        """Кольцо (труба) с отверстием: подшипники, втулки."""
        import math
        n0 = set(self.bm.faces)
        rot = Vector((0, 0, 1)).rotation_difference(Vector(axis)).to_matrix().to_4x4()
        mat = (m or Matrix()) @ Matrix.Translation(Vector(center)) @ rot
        rings = []
        for r, z in ((r_out, -h / 2), (r_out, h / 2), (r_in, h / 2), (r_in, -h / 2)):
            rings.append([self.bm.verts.new(mat @ Vector((r * math.cos(2 * math.pi * k / seg),
                                                          r * math.sin(2 * math.pi * k / seg), z)))
                          for k in range(seg)])
        for a, b in zip(rings, rings[1:] + rings[:1]):
            for k in range(seg):
                j = (k + 1) % seg
                self.bm.faces.new((a[k], a[j], b[j], b[k]))
        self._tag(n0)
        return self

    def sphere(self, center, r, scale=(1, 1, 1), m=None):
        n0 = set(self.bm.faces)
        mat = (m or Matrix()) @ Matrix.Translation(Vector(center)) @ Matrix.Diagonal((*scale, 1))
        bmesh.ops.create_uvsphere(self.bm, u_segments=32, v_segments=16, radius=r, matrix=mat)
        self._tag(n0)
        return self

    def stadium(self, p0, p1, r0, r1, y, m=None):
        """Плоская «кость» в плоскости XZ между (x,z)-точками, толщина по Y."""
        n0 = set(self.bm.faces)
        a0, a1 = Vector((p0[0], 0, p0[1])), Vector((p1[0], 0, p1[1]))
        d = a1 - a0
        n = Vector((-d.z, 0, d.x)).normalized()
        quad = (a0 + n * r0, a0 - n * r0, a1 - n * r1, a1 + n * r1)
        vs = [self.bm.verts.new((v.x, yy, v.z)) for yy in y for v in quad]
        if m:
            bmesh.ops.transform(self.bm, matrix=m, verts=vs)
        self.bm.faces.new(vs[:4])
        self.bm.faces.new(vs[4:][::-1])
        for i in range(4):
            j = (i + 1) % 4
            self.bm.faces.new((vs[j], vs[i], vs[4 + i], vs[4 + j]))
        self._tag(n0)
        yc, h = (y[0] + y[1]) / 2, y[1] - y[0]
        for p, r in ((a0, r0), (a1, r1)):
            self.cyl((p.x, yc, p.z), (0, 1, 0), r, h, m=m)
        return self

    def prism(self, pts, y, m=None):
        """Плоский многоугольник в плоскости XZ [(x, z), …] (выпуклый), толщина по Y."""
        n0 = set(self.bm.faces)
        vs = [self.bm.verts.new((x, yy, z)) for yy in y for x, z in pts]
        if m:
            bmesh.ops.transform(self.bm, matrix=m, verts=vs)
        k = len(pts)
        self.bm.faces.new(vs[:k])
        self.bm.faces.new(vs[k:][::-1])
        for i in range(k):
            j = (i + 1) % k
            self.bm.faces.new((vs[j], vs[i], vs[k + i], vs[k + j]))
        bmesh.ops.recalc_face_normals(self.bm, faces=[f for f in self.bm.faces if f not in n0])
        self._tag(n0)
        return self


MATS = {}


def mat(name, color, rough=0.5, metal=0.0, emit=0.0, alpha=1.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = emit
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*color, alpha)
    MATS[name] = m
    return m


COLS = {}


def col(path):
    """Коллекция по пути 'Servos/MG996R'; родители создаются автоматически."""
    if path in COLS:
        return COLS[path]
    parent = bpy.context.scene.collection
    if "/" in path:
        parent = col(path.rsplit("/", 1)[0])
    c = bpy.data.collections.new(path.rsplit("/", 1)[-1])
    parent.children.link(c)
    COLS[path] = c
    return c
