"""
NeuroPaw — build_v3.py
Этап 2: модель v3 с нуля по решениям из analysis_v2.md.
  - MG996R 40.7×19.7×42.9, вал сервы совпадает с осью сустава;
  - плечо (ось X) — серва внутри корпуса, бедро (ось Y) — в кронштейне плеча,
    колено — серва в бедре у тазобедренного узла, голень двигается тягой
    (параллелограмм: угол рычага сервы = углу колена);
  - все колени смотрят назад; иерархия суставов на пустышках (готово к MJCF);
  - полый корпус + крышка, электроника внутри, статичная голова.
Запуск: blender --background --python scripts/build_v3.py
Результат: robodog_v3.blend
"""
import bpy
import bmesh
import json
import math
import os
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(BASE, "params_v3.json")) as f:
    P = json.load(f)
OUT = os.path.join(BASE, "robodog_v3.blend")

MM = 0.001

# ── размеры, мм ───────────────────────────────────────────────────────────────
BL, BW = P["body"]["length"], P["body"]["width"]           # 260, 110
BACK_Z = P["stance"]["back_height_from_floor"]              # 220 — верх крышки
WALL, FLOOR, LID = 3.0, 2.5, 2.5   # дно/крышка тоньше: MG996R с лапками 54.5 мм
BODY_BOT = BACK_Z - P["body"]["height"]                     # 160
HX = P["shoulder_spacing"]["along_body"] / 2                # 105 — X оси бедра
UL, LLEN = P["leg"]["upper_length"], P["leg"]["lower_length"]
FOOT_R = P["leg"]["foot_diameter"] / 2

S_W, S_D = P["servo_mg996r"]["width"], P["servo_mg996r"]["depth"]  # 40.7, 19.7
S_CASE, S_SHAFT = 38.9, 4.0                                 # корпус + вал = 42.9
S_OFF = 10.0                                                # вал от центра корпуса

AXIS_Z = 180.0              # высота осей плеча и бедра (лапки плечевой сервы в корпусе)
SH_X = BL / 2 - WALL        # 127 — торец вала плечевой сервы (внутр. стенка)
SH_Y = 40.0                 # ось плеча (X) смещена вбок
HIP_SERVO_Y0 = 62.0         # внутренняя грань сервы бедра
SHAFT_Y = HIP_SERVO_Y0 + S_CASE          # 100.9 — торец корпуса, начало вала
PLATE_OUT = (SHAFT_Y + S_SHAFT, SHAFT_Y + S_SHAFT + 3)   # наружная щека бедра
PLATE_IN = (57.5, 60.5)                                  # внутренняя щека
LEG_Y = (HIP_SERVO_Y0 + SHAFT_Y) / 2                     # 81.5 — плоскость ноги
KNEE_SERVO_D = 40.0         # вал коленной сервы от оси бедра вдоль бедра
ARM = 18.0                  # плечо качалки сервы и рычага голени
LINK_Y = (PLATE_OUT[1] + 0.5, PLATE_OUT[1] + 3.0)        # слой качалки/рычага
ROD_Y = LINK_Y[1] + 1.5

# ── поза стоя: стопа под осью бедра, колено назад ────────────────────────────
D_HF = AXIS_Z - FOOT_R
HIP_A = math.acos((UL**2 + D_HF**2 - LLEN**2) / (2 * UL * D_HF))
_kx, _kz = -UL * math.sin(HIP_A), -UL * math.cos(HIP_A)
SHIN_WORLD = math.atan2(-(0 - _kx), -(-D_HF - _kz))      # из (−sinθ, −cosθ)
KNEE_A = SHIN_WORLD - HIP_A
# направление качалки в покое: в позе стоя перпендикулярна бедру (вперёд)
ARM_DIR = Vector((math.cos(-KNEE_A), 0, -math.sin(-KNEE_A)))

LEGS = {"FL": (1, 1), "FR": (1, -1), "RL": (-1, 1), "RR": (-1, -1)}


# ══════════════════════════════════════════════════════════════════════════════
# helpers
# ══════════════════════════════════════════════════════════════════════════════
def frame(origin, z_axis, x_axis):
    z = Vector(z_axis).normalized()
    x = Vector(x_axis).normalized()
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def rng(a, b, s=1):
    return tuple(sorted((a * s, b * s)))


def box(bm, x, y, z, m=None):
    """Параллелепипед по диапазонам (мм) в координатах m."""
    c = Vector(((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2))
    s = Matrix.Diagonal((x[1] - x[0], y[1] - y[0], z[1] - z[0], 1))
    mat = (m or Matrix()) @ Matrix.Translation(c) @ s
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


def cyl(bm, center, axis, r, h, seg=32, m=None):
    rot = Vector((0, 0, 1)).rotation_difference(Vector(axis)).to_matrix().to_4x4()
    mat = (m or Matrix()) @ Matrix.Translation(center) @ rot
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r, radius2=r, depth=h, matrix=mat)


def sphere(bm, center, r, scale=(1, 1, 1)):
    mat = Matrix.Translation(center) @ Matrix.Diagonal((*scale, 1))
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r, matrix=mat)


def stadium(bm, p0, p1, r0, r1, y, m=None):
    """Плоская «кость» в плоскости XZ между точками p0, p1 (x,z), толщина по y."""
    p0, p1 = Vector((p0[0], 0, p0[1])), Vector((p1[0], 0, p1[1]))
    d = p1 - p0
    yc, h = (y[0] + y[1]) / 2, y[1] - y[0]
    n = Vector((-d.z, 0, d.x)).normalized()
    a, b = p0 + n * r0, p0 - n * r0
    c, e = p1 - n * r1, p1 + n * r1
    verts = []
    for yy in y:
        verts += [bm.verts.new((v.x, yy, v.z)) for v in (a, b, c, e)]
    if m:
        bmesh.ops.transform(bm, matrix=m, verts=verts)
    f = [bm.faces.new(verts[:4]), bm.faces.new(verts[4:][::-1])]
    for i in range(4):
        j = (i + 1) % 4
        f.append(bm.faces.new((verts[j], verts[i], verts[4 + i], verts[4 + j])))
    for p, r in ((p0, r0), (p1, r1)):
        cyl(bm, Vector((p.x, yc, p.z)), (0, 1, 0), r, h, m=m)


def servo(bm, m):
    """MG996R. Локально: вал по +Z из начала координат, корпус уходит в −X, −Z."""
    box(bm, (-S_OFF - S_W / 2, -S_OFF + S_W / 2), (-S_D / 2, S_D / 2), (-S_CASE, 0), m)
    box(bm, (-S_OFF - 27.25, -S_OFF + 27.25), (-S_D / 2, S_D / 2), (-11, -8.5), m)
    cyl(bm, Vector((0, 0, 1)), (0, 0, 1), 6.0, 2.0, m=m)         # бобышка
    cyl(bm, Vector((0, 0, S_SHAFT / 2)), (0, 0, 1), 3.0, S_SHAFT, 24, m=m)


MATS = {}


def mat(name, color, rough=0.5, metal=0.0, emit=0.0):
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
    m.diffuse_color = (*color, 1)
    MATS[name] = m
    return m


COLS = {}


def col(name):
    if name not in COLS:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        COLS[name] = c
    return COLS[name]


REST = {}     # объект → мировая позиция начала (мм) в позе покоя
LINK = {}     # имя меш-объекта → звено (для проверки пересечений)


def empty(name, world_mm, parent=None, collection="Rig", size=12):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'ARROWS'
    e.empty_display_size = size * MM
    col(collection).objects.link(e)
    e.parent = parent
    REST[name] = Vector(world_mm)
    base = REST[parent.name] if parent else Vector()
    e.location = (Vector(world_mm) - base) * MM
    return e


def obj(name, build, material, parent, collection, link, bevel=0.0):
    """build(bm) пишет геометрию в мировых мм позы покоя."""
    bm = bmesh.new()
    build(bm)
    off = REST[parent.name]
    bmesh.ops.transform(bm, matrix=Matrix.Scale(MM, 4) @ Matrix.Translation(-off),
                        verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(material)
    col(collection).objects.link(o)
    o.parent = parent
    if bevel:
        mod = o.modifiers.new("Bevel", 'BEVEL')
        mod.width = bevel * MM
        mod.segments = 3
        mod.limit_method = 'ANGLE'
    for p in o.data.polygons:
        p.use_smooth = True
    LINK[name] = link
    return o


# ══════════════════════════════════════════════════════════════════════════════
# сцена
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'

M_BODY = mat("PETG_white", (0.85, 0.86, 0.84), 0.42)
M_ACC = mat("PETG_orange", (0.95, 0.33, 0.05), 0.4)
M_SHIN = mat("PETG_graphite", (0.06, 0.06, 0.07), 0.45)
M_SERVO = mat("Servo_black", (0.02, 0.02, 0.02), 0.55)
M_HORN = mat("Nylon_horn", (0.9, 0.9, 0.87), 0.6)
M_TPU = mat("TPU_black", (0.03, 0.03, 0.03), 0.9)
M_METAL = mat("Steel", (0.75, 0.75, 0.77), 0.28, 1.0)
M_PCB = mat("PCB_green", (0.02, 0.22, 0.08), 0.5)
M_PCB_B = mat("PCB_blue", (0.02, 0.07, 0.35), 0.5)
M_BAT = mat("Battery", (0.15, 0.17, 0.2), 0.6)
M_GLASS = mat("Face_glass", (0.005, 0.005, 0.008), 0.06)
M_EYE = mat("Eye_display", (0.15, 0.75, 1.0), 0.3, emit=4.0)
M_LENS = mat("Lens", (0.02, 0.03, 0.05), 0.05, 0.6)

root = empty("NeuroPaw_root", (0, 0, 0), collection="Rig", size=40)

# ── корпус ────────────────────────────────────────────────────────────────────
hb, hw = BL / 2, BW / 2
TOP = BACK_Z - LID
obj("Body_floor", lambda bm: box(bm, (-hb, hb), (-hw, hw), (BODY_BOT, BODY_BOT + FLOOR)),
    M_BODY, root, "Body", "body", 2.0)
for s, nm in ((1, "L"), (-1, "R")):
    obj(f"Body_wall_{nm}", lambda bm, s=s: box(bm, (-hb, hb), rng(hw - WALL, hw, s),
                                               (BODY_BOT, TOP)), M_BODY, root, "Body", "body", 1.5)
for s, nm in ((1, "F"), (-1, "B")):
    obj(f"Body_end_{nm}", lambda bm, s=s: box(bm, rng(hb - WALL, hb, s), (-hw + WALL, hw - WALL),
                                              (BODY_BOT, TOP)), M_BODY, root, "Body", "body", 1.5)
obj("Body_lid", lambda bm: box(bm, (-hb, hb), (-hw, hw), (TOP, BACK_Z)),
    M_BODY, root, "Body", "body", 2.5)

# ── электроника ───────────────────────────────────────────────────────────────
F = BODY_BOT + FLOOR          # 162.5 — пол изнутри
E = P["electronics"]
ELEC = [  # имя, ключ, x0, y0, z0, материал
    ("Battery_2S", "battery_2s_5000mah", -70, -22.5, F, M_BAT),
    ("ESP32_S3", "esp32_s3_devkit", -68, 6, F + 28, M_PCB),
    ("PCA9685", "pca9685", -70, -32.5, F + 28, M_PCB_B),
    ("UBEC_6V", "ubec", 15, -15, F + 28, M_BAT),
    ("IMU_BNO085", "imu_bno085", -9, -10, F + 28, M_PCB_B),
]
for name, key, x0, y0, z0, m in ELEC:
    d = E[key]
    obj(name, lambda bm, d=d, x0=x0, y0=y0, z0=z0:
        box(bm, (x0, x0 + d["length"]), (y0, y0 + d["width"]), (z0, z0 + d["height"])),
        m, root, "Electronics", "body")
# стойки под платы
obj("Standoffs", lambda bm: [cyl(bm, Vector((x, y, F + 26.5)), (0, 0, 1), 2.5, 3)
                             for x in (-64, -16, 19, 61) for y in (-28, 28)],
    M_METAL, root, "Electronics", "body")

# ── голова (статичная) ────────────────────────────────────────────────────────
HF = 207.0     # передняя грань лица
EYE_Y, EYE_Z, EYE_R = 24.0, 238.0, 16.25     # GC9A01 1.28"


def head_shell(bm):
    box(bm, (140, HF - 2), (-47, 47), (204, 264))


obj("Neck_mount", lambda bm: box(bm, (100, 150), (-20, 20), (BACK_Z, 210)),
    M_ACC, root, "Head", "head", 3.0)
obj("Head_shell", head_shell, M_BODY, root, "Head", "head", 12.0)
obj("Head_face", lambda bm: box(bm, (HF - 2, HF), (-43, 43), (214, 258)),
    M_GLASS, root, "Head", "head", 4.0)
obj("Muzzle", lambda bm: box(bm, (HF - 6, HF + 30), (-25, 25), (204, 228)),
    M_BODY, root, "Head", "head", 8.0)
obj("Eyes_GC9A01", lambda bm: [cyl(bm, Vector((HF + 0.4, s * EYE_Y, EYE_Z)), (1, 0, 0), EYE_R, 0.8, 48)
                               for s in (1, -1)], M_EYE, root, "Head", "head")
obj("Camera_IMX219", lambda bm: (box(bm, (HF - 12, HF - 3), (-12.5, 12.5), (EYE_Z - 12, EYE_Z + 12)),
                                 cyl(bm, Vector((HF + 2, 0, EYE_Z)), (1, 0, 0), 4.2, 6, 32)),
    M_LENS, root, "Head", "head")
obj("Nose_VL53L5CX", lambda bm: box(bm, (HF + 30, HF + 33), (-5, 5), (213, 223)),
    M_LENS, root, "Head", "head")
for s, nm in ((1, "L"), (-1, "R")):
    def ear(bm, s=s):
        m = Matrix.Translation((160, s * 31, 254)) @ Matrix.Rotation(math.radians(-s * 18), 4, 'X')
        box(bm, (-12, 12), (-3, 3), (0, 26), m)
    obj(f"Ear_{nm}", ear, M_ACC, root, "Head", "head", 2.5)

# ── ноги ──────────────────────────────────────────────────────────────────────
FOOT_W = {}
for leg, (xs, ys) in LEGS.items():
    C = f"Leg_{leg}"
    hx = xs * HX

    # плечо: серва внутри корпуса, вал по ±X сквозь торцевую стенку
    obj(f"{leg}_shoulder_servo", lambda bm: servo(bm, frame((xs * SH_X, ys * SH_Y, AXIS_Z),
                                                             (xs, 0, 0), (0, 0, -1))),
        M_SERVO, root, C, "body")
    sh = empty(f"{leg}_shoulder", (xs * SH_X, ys * SH_Y, AXIS_Z), root)

    # кронштейн плеча: качалка + торцевая пластина + рамка под серву бедра
    def bracket(bm):
        cyl(bm, Vector((xs * (SH_X + 5), ys * SH_Y, AXIS_Z)), (1, 0, 0), 11, 2)
        box(bm, rng(SH_X + 6, SH_X + 9, xs), rng(28, 96, ys), (AXIS_Z - 12, AXIS_Z + 41))
        box(bm, rng(HX - 13, SH_X + 9, xs), rng(86.5, 89.5, ys), (AXIS_Z + 30.5, AXIS_Z + 41))
        box(bm, rng(HX + 10, SH_X + 9, xs), rng(86.5, 89.5, ys), (AXIS_Z - 11, AXIS_Z + 41))
    obj(f"{leg}_shoulder_bracket", bracket, M_ACC, sh, C, f"{leg}_bracket", 1.2)
    obj(f"{leg}_hip_servo", lambda bm: servo(bm, frame((hx, ys * SHAFT_Y, AXIS_Z),
                                                        (0, ys, 0), (0, 0, -1))),
        M_SERVO, sh, C, f"{leg}_bracket")

    # бедро: две щёки, коленная серва внутри, стяжка над коленом
    hip = empty(f"{leg}_hip", (hx, ys * LEG_Y, AXIS_Z), sh)
    hz = AXIS_Z

    def thigh(bm):
        for y in (PLATE_OUT, PLATE_IN):
            stadium(bm, (hx, hz), (hx, hz - UL), 14, 10, rng(*y, ys))
        box(bm, (hx - 7, hx + 7), rng(PLATE_IN[1], PLATE_OUT[0], ys), (hz - 92, hz - 82))
    obj(f"{leg}_thigh", thigh, M_ACC, hip, C, f"{leg}_thigh", 1.0)
    obj(f"{leg}_knee_servo", lambda bm: servo(bm, frame((hx, ys * SHAFT_Y, hz - KNEE_SERVO_D),
                                                         (0, ys, 0), (0, 0, 1))),
        M_SERVO, hip, C, f"{leg}_thigh")

    # качалка коленной сервы (повторяет угол колена) и удлинитель вала
    kd = empty(f"{leg}_knee_drive", (hx, ys * LEG_Y, hz - KNEE_SERVO_D), hip, size=6)
    ks = Vector((hx, 0, hz - KNEE_SERVO_D))
    tip_h = ks + ARM_DIR * ARM

    def horn(bm):
        cyl(bm, Vector((hx, ys * (PLATE_OUT[1] + 0.25), ks.z)), (0, 1, 0), 3.5, PLATE_OUT[1] - SHAFT_Y)
        stadium(bm, (ks.x, ks.z), (tip_h.x, tip_h.z), 7, 4, rng(*LINK_Y, ys))
    obj(f"{leg}_knee_horn", horn, M_HORN, kd, C, f"{leg}_horn")

    # голень: кость, ось колена, рычаг тяги, стопа TPU
    knee = empty(f"{leg}_knee", (hx, ys * LEG_Y, hz - UL), hip)
    kz = hz - UL
    tip_l = Vector((hx, 0, kz)) + ARM_DIR * ARM
    obj(f"{leg}_shin", lambda bm: stadium(bm, (hx, kz), (hx, kz - LLEN + FOOT_R), 10, 6.5,
                                          rng(LEG_Y - 10, LEG_Y + 10, ys)),
        M_SHIN, knee, C, f"{leg}_shin", 1.0)
    obj(f"{leg}_knee_lever", lambda bm: (stadium(bm, (hx, kz), (tip_l.x, tip_l.z), 6.5, 4,
                                                 rng(*LINK_Y, ys)),
                                         cyl(bm, Vector((hx, ys * (PLATE_IN[0] + LINK_Y[1]) / 2, kz)),
                                             (0, 1, 0), 3.0, LINK_Y[1] - PLATE_IN[0])),
        M_METAL, knee, C, f"{leg}_lever")
    obj(f"{leg}_foot", lambda bm: sphere(bm, Vector((hx, ys * LEG_Y, kz - LLEN)), FOOT_R,
                                         (1, 1.1, 0.9)), M_TPU, knee, C, f"{leg}_shin")

    # тяга: от конца качалки к концу рычага (Stretch To)
    tgt = empty(f"{leg}_rod_target", (tip_l.x, ys * ROD_Y, tip_l.z), knee, size=4)
    rod_len = (tip_l - tip_h).length
    rod_e = empty(f"{leg}_rod_root", (tip_h.x, ys * ROD_Y, tip_h.z), kd, size=4)

    def rod(bm):
        o = Vector((tip_h.x, ys * ROD_Y, tip_h.z))
        cyl(bm, o + Vector((0, rod_len / 2, 0)), (0, 1, 0), 1.6, rod_len, 16)
        for t in (0, rod_len):
            cyl(bm, o + Vector((0, t, 0)), (0, 0, 1), 3.2, 3.0, 24)
    r = obj(f"{leg}_rod", rod, M_METAL, rod_e, C, f"{leg}_rod")
    c = r.constraints.new('STRETCH_TO')
    c.target, c.rest_length, c.volume = tgt, rod_len * MM, 'NO_VOLUME'

    cr = kd.constraints.new('COPY_ROTATION')
    cr.target, cr.use_x, cr.use_z = knee, False, False
    cr.owner_space = cr.target_space = 'LOCAL'

    # поза стоя
    hip.rotation_euler.y = HIP_A
    knee.rotation_euler.y = KNEE_A
    FOOT_W[leg] = knee

# пол для рендера
fl = bpy.data.meshes.new("Floor")
bm = bmesh.new()
box(bm, (-600, 600), (-600, 600), (-2, 0))
bmesh.ops.transform(bm, matrix=Matrix.Scale(MM, 4), verts=bm.verts)
bm.to_mesh(fl)
bm.free()
floor = bpy.data.objects.new("Floor", fl)
floor.data.materials.append(mat("Floor", (0.55, 0.56, 0.58), 0.8))
scene.collection.objects.link(floor)

# ══════════════════════════════════════════════════════════════════════════════
# проверки
# ══════════════════════════════════════════════════════════════════════════════
dg = bpy.context.evaluated_depsgraph_get()
dg.update()
print(f"[v3] стойка: бедро {math.degrees(HIP_A):.1f}°, колено {math.degrees(KNEE_A):.1f}°")
for leg, knee in FOOT_W.items():
    p = knee.matrix_world @ Vector((0, 0, -LLEN * MM))
    print(f"[v3] стопа {leg}: ({p.x / MM:.1f}, {p.y / MM:.1f}, {p.z / MM:.1f}) мм  "
          f"(ось бедра X={LEGS[leg][0] * HX:.0f})")
for leg in LEGS:
    r = bpy.data.objects[f"{leg}_rod"]
    t = bpy.data.objects[f"{leg}_rod_target"]
    gap = (r.matrix_world @ Vector((0, r.constraints[0].rest_length, 0))) - t.matrix_world.translation
    print(f"[v3] тяга {leg}: конец до рычага {gap.length / MM:.2f} мм, "
          f"масштаб {r.matrix_world.to_scale().y:.3f}")

# пересечения между разными звеньями (касания по конструкции — в белом списке)
ALLOWED = {tuple(sorted(p)) for p in (("thigh", "horn"), ("thigh", "lever"), ("bracket", "thigh"),
                                      ("horn", "rod"), ("lever", "rod"), ("lever", "shin"),
                                      ("body", "bracket"), ("body", "head"))}
trees = {}
for o in scene.objects:
    if o.type == 'MESH' and o.name in LINK:
        me = o.evaluated_get(dg).to_mesh()
        mw = o.matrix_world
        trees[o.name] = BVHTree.FromPolygons([mw @ v.co for v in me.vertices],
                                             [p.vertices[:] for p in me.polygons])
        o.evaluated_get(dg).to_mesh_clear()
names = sorted(trees)
hits = []
for i, a in enumerate(names):
    for b in names[i + 1:]:
        la, lb = LINK[a], LINK[b]
        if la == lb:
            continue
        ka = tuple(sorted((la.split("_")[-1], lb.split("_")[-1])))
        same_leg = la[:2] == lb[:2] or "body" in (la, lb) or "head" in (la, lb)
        if same_leg and ka in ALLOWED:
            continue
        if trees[a].overlap(trees[b]):
            hits.append((a, b))
print(f"[v3] пересечений между звеньями: {len(hits)}")
for a, b in hits:
    print(f"      {a}  ×  {b}")

for leg in LEGS:
    zs = [(bpy.data.objects[f"{leg}_shoulder_servo"].matrix_world @ v.co).z / MM
          for v in bpy.data.objects[f"{leg}_shoulder_servo"].data.vertices]
    ok = min(zs) >= BODY_BOT + FLOOR and max(zs) <= BACK_Z - LID
    print(f"[v3] плечевая серва {leg}: Z {min(zs):.2f}…{max(zs):.2f} — {'внутри' if ok else 'ВЫЛЕЗАЕТ'}")
xs = [o.matrix_world @ v.co for o in scene.objects if o.type == 'MESH' and o.name != "Floor"
      for v in o.data.vertices]
lo = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs))) / MM
hi = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs))) / MM
print(f"[v3] габарит: {hi.x - lo.x:.0f} × {hi.y - lo.y:.0f} × {hi.z - lo.z:.0f} мм, низ Z={lo.z:.1f}")

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"[v3] сохранено: {OUT}")
