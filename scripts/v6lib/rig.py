"""Арматура v6: одна кость на сустав, ось кости (локальная Y) = ось вала.

Поворот сустава — rotation_euler.y кости. Детали звена привязаны к кости,
начало объекта — в точке сустава (пивот на оси вала).
"""
import bmesh
import bpy
from mathutils import Matrix, Vector

from .geom import MM

BONE_LEN = 20.0
ARM = None
LINK = {}      # имя объекта → имя кости (звено) для проверки пересечений


def build(name, bones, collection):
    """bones: [(имя, голова_мм, ось, родитель|None)]"""
    global ARM
    data = bpy.data.armatures.new(name)
    data.display_type = 'STICK'
    ARM = bpy.data.objects.new(name, data)
    ARM.show_in_front = True
    collection.objects.link(ARM)
    bpy.context.view_layer.objects.active = ARM
    ARM.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for bname, head, axis, parent in bones:
        eb = data.edit_bones.new(bname)
        h = Vector(head)
        eb.head = h * MM
        eb.tail = (h + Vector(axis).normalized() * BONE_LEN) * MM
        eb.roll = 0.0
        if parent:
            eb.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in ARM.pose.bones:
        pb.rotation_mode = 'XYZ'
    return ARM


def make(name, mesh, collection, bone, origin=None, bevel=0.0, props=None, cut=None):
    """Создаёт объект из geom.Mesh (мировые мм) и привязывает к кости.

    cut — geom.Mesh в тех же координатах: вычитается булевой операцией (отверстия, окна).
    """
    b = ARM.data.bones[bone]
    origin = Vector(origin) if origin is not None else b.head_local / MM
    bm = mesh.bm
    bmesh.ops.transform(bm, matrix=Matrix.Scale(MM, 4) @ Matrix.Translation(-origin),
                        verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mesh.mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=0.6)
    o = bpy.data.objects.new(name, me)
    collection.objects.link(o)
    if cut is not None:
        _subtract(o, cut, origin)
    attach(o, bone, origin)
    if bevel:
        mod = o.modifiers.new("Bevel", 'BEVEL')
        mod.width = bevel * MM
        mod.segments = 3
        mod.limit_method = 'ANGLE'
        mod.harden_normals = True
    for k, v in (props or {}).items():
        o[k] = v
    LINK[name] = bone
    return o


def _subtract(o, cut, origin):
    """Булево вычитание cut из o (оба без родителя, в одних локальных координатах)."""
    bm = cut.bm
    bmesh.ops.transform(bm, matrix=Matrix.Scale(MM, 4) @ Matrix.Translation(-origin), verts=bm.verts)
    cme = bpy.data.meshes.new(o.name + "_cut")
    bm.to_mesh(cme)
    bm.free()
    co = bpy.data.objects.new(o.name + "_cut", cme)
    bpy.context.scene.collection.objects.link(co)
    mod = o.modifiers.new("Cut", 'BOOLEAN')
    mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', co
    mod.use_self, mod.use_hole_tolerant = True, True       # детали — объединения пересекающихся примитивов
    bpy.context.view_layer.update()
    new = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    old = o.data
    o.modifiers.remove(mod)
    o.data = new
    new.name = old.name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(co)
    bpy.data.meshes.remove(cme)
    for p in new.polygons:
        p.use_smooth = True
    new.set_sharp_from_angle(angle=0.6)


def attach(o, bone, origin_mm):
    b = ARM.data.bones[bone]
    o.parent = ARM
    o.parent_type = 'BONE'
    o.parent_bone = bone
    pm = ARM.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    o.matrix_parent_inverse = pm.inverted()
    o.matrix_basis = Matrix.Translation(Vector(origin_mm) * MM)


def pose(angles_deg):
    """{кость: угол°} — поворот вокруг оси вала."""
    import math
    for pb in ARM.pose.bones:
        pb.rotation_euler = (0, 0, 0)
    for k, a in angles_deg.items():
        ARM.pose.bones[k].rotation_euler.y = math.radians(a)
    bpy.context.view_layer.update()


def limit(bone, lo_deg, hi_deg):
    """Limit Rotation по оси вала (локальная Y) — программный предел хода."""
    import math
    c = ARM.pose.bones[bone].constraints.new('LIMIT_ROTATION')
    c.use_limit_y = True
    c.min_y, c.max_y = math.radians(lo_deg), math.radians(hi_deg)
    c.owner_space = 'LOCAL'
    c.name = "Servo_range"
    return c
