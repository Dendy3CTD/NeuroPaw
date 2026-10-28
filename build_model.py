"""
NeuroPaw — build_model.py  v2
Собирает 3D-модель четвероногой робособаки (без головы) в Blender 5.
Запуск: blender --background --python build_model.py
"""

import bpy
import json
import math
import os

# ── пути ──────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PARAMS_F  = os.path.join(BASE_DIR, "params.json")
BLEND_OUT = os.path.join(BASE_DIR, "robodog_v2.blend")
RENDERS   = os.path.join(BASE_DIR, "renders")
MESHES    = os.path.join(BASE_DIR, "meshes")
os.makedirs(RENDERS, exist_ok=True)
os.makedirs(MESHES,  exist_ok=True)

with open(PARAMS_F) as f:
    P = json.load(f)

mm = 0.001  # мм → м

BL = P["body"]["length"]  * mm   # 0.260
BW = P["body"]["width"]   * mm   # 0.110
BH = P["body"]["height"]  * mm   # 0.060

SL = P["shoulder_spacing"]["along_body"]  * mm   # 0.210
SW = P["shoulder_spacing"]["across_body"] * mm   # 0.110

UL = P["leg"]["upper_length"]  * mm   # 0.110  бедро
LL = P["leg"]["lower_length"]  * mm   # 0.120  голень
FD = P["leg"]["foot_diameter"] * mm   # 0.020  диаметр стопы

SRW = P["servo_mg996r"]["width"]  * mm   # 0.0407
SRD = P["servo_mg996r"]["depth"]  * mm   # 0.0197
SRH = P["servo_mg996r"]["height"] * mm   # 0.0429

# Спина (верх корпуса) на 220 мм от пола → центр корпуса ниже
BACK_H = P["stance"]["back_height_from_floor"] * mm   # 0.220
body_z = BACK_H - BH / 2                              # 0.190 м от пола

# Ноги выходят с нижней поверхности корпуса
HIP_Z = body_z - BH / 2    # 0.160 м — высота шарнира бедра от пола


# ══════════════════════════════════════════════════════════════════════════════
# Геометрия ноги в позе стоя (согнутое колено ~90°)
# ══════════════════════════════════════════════════════════════════════════════
# Бедро наклонено ВПЕРЁД по X на угол HIP_ANGLE от вертикали.
# Голень рассчитывается так, чтобы стопа оказалась на уровне пола.
# «Вперёд» для FL/FR = +X, для RL/RR = -X.

HIP_ANGLE = math.radians(35)   # наклон бедра от вертикали

def leg_geometry(sx, sy, fwd_sign):
    """
    sx, sy  — позиция шарнира бедра (hip pivot)
    fwd_sign — +1 передние ноги (lean forward), -1 задние (lean backward)
    Возвращает: knee_pos, shin_dir_xz, foot_pos
    """
    # Колено
    kx = sx + fwd_sign * UL * math.sin(HIP_ANGLE)
    kz = HIP_Z - UL * math.cos(HIP_ANGLE)

    # Стопа касается пола → foot_z = FD/2
    dz = FD / 2 - kz                                    # < 0 (вниз)
    horiz = math.sqrt(max(LL**2 - dz**2, 0))
    # Голень уходит назад (противоположно наклону бедра)
    fx = kx - fwd_sign * horiz
    fz = FD / 2

    shin_dx = fx - kx
    shin_dz = fz - kz
    shin_len = math.sqrt(shin_dx**2 + shin_dz**2)

    knee_pos = (kx, sy, kz)
    foot_pos = (fx, sy, fz)
    # угол голени от вертикали (для поворота объекта)
    shin_angle_from_vert = math.atan2(abs(shin_dx), abs(shin_dz))

    return knee_pos, foot_pos, shin_angle_from_vert, shin_dx, shin_dz


# ══════════════════════════════════════════════════════════════════════════════
# Утилиты
# ══════════════════════════════════════════════════════════════════════════════

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def new_col(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def link(obj, col):
    col.objects.link(obj)
    if obj.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(obj)


def make_mat(name, rgba, alpha=1.0, metallic=0.0, roughness=0.5):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if alpha < 1.0:
        mat.blend_method = 'BLEND'
        mat.use_backface_culling = False
    return mat


def box(name, loc, size, mat, col):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name; o.scale = size
    o.data.materials.append(mat)
    link(o, col); return o


def sphere(name, loc, r, mat, col):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc,
                                          segments=24, ring_count=16)
    o = bpy.context.active_object
    o.name = name; o.data.materials.append(mat)
    link(o, col); return o


def cylinder(name, loc, r, depth, mat, col, rot=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth,
                                         location=loc, rotation=rot,
                                         vertices=16)
    o = bpy.context.active_object
    o.name = name; o.data.materials.append(mat)
    link(o, col); return o


def rod(name, p0, p1, radius, mat, col):
    """Цилиндр между двумя точками."""
    dx, dy, dz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
    length = math.sqrt(dx*dx+dy*dy+dz*dz)
    if length < 1e-6:
        return None
    mx = (p0[0]+p1[0])/2
    my = (p0[1]+p1[1])/2
    mz = (p0[2]+p1[2])/2
    # поворот: Z → направление стержня
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        rot = (0, 0, 0) if dz > 0 else (math.pi, 0, 0)
    else:
        rot_y = math.atan2(math.sqrt(dx*dx+dy*dy), dz)
        rot_z = math.atan2(dy, dx)
        rot = (0, rot_y, rot_z)
    return cylinder(name, (mx,my,mz), radius, length, mat, col, rot=rot)


def arrow_axis(name, origin, axis_dir, length, col):
    mat_ax = make_mat("mat_axis", (1, 0.85, 0, 1))
    p1 = tuple(origin[i] + axis_dir[i]*length for i in range(3))
    rod(name+"_rod", origin, p1, 0.0015, mat_ax, col)
    # конус
    bpy.ops.mesh.primitive_cone_add(
        radius1=0.004, radius2=0, depth=0.008, location=p1)
    tip = bpy.context.active_object
    tip.name = name+"_tip"
    tip.data.materials.append(mat_ax)
    link(tip, col)


def text3d(name, body, loc, size, col):
    bpy.ops.object.text_add(location=loc)
    o = bpy.context.active_object
    o.name = name; o.data.body = body; o.data.size = size
    mat = make_mat("mat_label", (0.05, 0.05, 0.05, 1))
    o.data.materials.append(mat)
    link(o, col)


# ══════════════════════════════════════════════════════════════════════════════
# Материалы
# ══════════════════════════════════════════════════════════════════════════════
mat_petg  = make_mat("PETG",    (0.80, 0.82, 0.88, 0.40), alpha=0.40)
mat_tpu   = make_mat("TPU",     (0.15, 0.15, 0.15, 1.0),  roughness=0.9)
mat_servo = make_mat("Servo",   (0.85, 0.06, 0.06, 1.0),  roughness=0.4)
mat_bat   = make_mat("Battery", (0.15, 0.30, 0.80, 1.0))
mat_elec  = make_mat("Elec",    (0.10, 0.65, 0.15, 1.0))
mat_sens  = make_mat("Sensor",  (0.80, 0.60, 0.05, 1.0))

# ══════════════════════════════════════════════════════════════════════════════
# Сцена
# ══════════════════════════════════════════════════════════════════════════════
clear_scene()
c_body   = new_col("Body")
c_elec   = new_col("Electronics")
c_legs   = new_col("Legs")
c_axes   = new_col("Axes")
c_labels = new_col("Labels")

# ── пол для ориентации ────────────────────────────────────────────────────────
mat_floor = make_mat("Floor", (0.70, 0.70, 0.70, 1.0), roughness=0.9)
bpy.ops.mesh.primitive_plane_add(size=0.8, location=(0, 0, 0))
fl = bpy.context.active_object
fl.name = "Floor"; fl.data.materials.append(mat_floor)
link(fl, c_body)

# ══════════════════════════════════════════════════════════════════════════════
# КОРПУС
# ══════════════════════════════════════════════════════════════════════════════
body = box("Body_main", (0, 0, body_z), (BL, BW, BH), mat_petg, c_body)

E = P["electronics"]

# батарея — центр-низ корпуса
bat_h = E["battery_2s_5000mah"]["height"] * mm
bat = box("Battery_2S",
          (0, 0, body_z - BH/2 + bat_h/2),
          (E["battery_2s_5000mah"]["length"]*mm,
           E["battery_2s_5000mah"]["width"]*mm,
           bat_h),
          mat_bat, c_elec)

# остальная электроника — стопка в верхней части корпуса
for key, tag, offset_x in [
    ("esp32_s3_devkit", "ESP32-S3", -0.050),
    ("pca9685",         "PCA9685",  -0.010),
    ("ubec",            "UBEC",      0.025),
    ("imu_bno085",      "IMU",       0.060),
]:
    e = E[key]
    box(tag, (offset_x, 0, body_z + BH/2 - e["height"]*mm/2 - 0.002),
        (e["length"]*mm, e["width"]*mm, e["height"]*mm),
        mat_elec, c_elec)

# датчик расстояния — морда
vl = E["vl53l5cx"]
box("VL53L5CX",
    (BL/2 + vl["length"]*mm/2, 0, body_z),
    (vl["length"]*mm, vl["width"]*mm, vl["height"]*mm),
    mat_sens, c_elec)


# ══════════════════════════════════════════════════════════════════════════════
# СТРОИМ НОГИ
# ══════════════════════════════════════════════════════════════════════════════

legs_cfg = [
    #  tag    shoulder_x  shoulder_y  side_sign  fwd_sign
    ("FL",  +SL/2,  +SW/2,  +1,  +1),
    ("FR",  +SL/2,  -SW/2,  -1,  +1),
    ("RL",  -SL/2,  +SW/2,  +1,  -1),
    ("RR",  -SL/2,  -SW/2,  -1,  -1),
]

THIGH_R = 0.007   # радиус трубки бедра/голени

for tag, sh_x, sh_y, side, fwd in legs_cfg:

    # ── плечевая серва (shoulder) — ось вдоль X ──────────────────────────────
    sh_pos = (sh_x, sh_y, body_z)
    box(f"{tag}_sh_servo", sh_pos, (SRD, SRW, SRH), mat_servo, c_legs)
    text3d(f"lbl_{tag}_sh", f"{tag}_shoulder",
           (sh_x - 0.005, sh_y + side*(SRW/2 + 0.005), body_z + SRH/2),
           0.004, c_labels)
    arrow_axis(f"ax_{tag}_sh", sh_pos, (1, 0, 0), 0.035, c_axes)

    # ── кронштейн — PETG-плашка соединяет shoulder → hip ────────────────────
    hip_y = sh_y + side * (SRW/2 + 0.006 + SRD/2)
    hip_pos = (sh_x, hip_y, HIP_Z)
    bracket = box(f"{tag}_bracket",
                  (sh_x, (sh_y + hip_y)/2, (body_z + HIP_Z)/2),
                  (0.013, abs(hip_y - sh_y), 0.008),
                  mat_petg, c_legs)

    # ── бедренная серва (hip) — ось вдоль Y ──────────────────────────────────
    box(f"{tag}_hip_servo", hip_pos, (SRD, SRW, SRH), mat_servo, c_legs)
    text3d(f"lbl_{tag}_hip", f"{tag}_hip",
           (sh_x - 0.005, hip_y + side*(SRW/2 + 0.005), HIP_Z + SRH/2),
           0.004, c_labels)
    arrow_axis(f"ax_{tag}_hip", hip_pos, (0, side, 0), 0.035, c_axes)

    # ── бедро (трубка до колена) ──────────────────────────────────────────────
    knee_pos, foot_pos, shin_ang, sdx, sdz = leg_geometry(sh_x, hip_y, fwd)

    thigh_mid = ((hip_pos[0] + knee_pos[0])/2,
                 hip_y,
                 (HIP_Z + knee_pos[2])/2)
    rod(f"{tag}_thigh", hip_pos, knee_pos, THIGH_R, mat_petg, c_legs)

    # ── коленная серва ────────────────────────────────────────────────────────
    box(f"{tag}_kn_servo", knee_pos, (SRD, SRW, SRH), mat_servo, c_legs)
    text3d(f"lbl_{tag}_kn", f"{tag}_knee",
           (knee_pos[0] - 0.005, knee_pos[1] + side*(SRW/2 + 0.005),
            knee_pos[2] + SRH/2),
           0.004, c_labels)
    arrow_axis(f"ax_{tag}_kn", knee_pos, (0, side, 0), 0.035, c_axes)

    # ── голень (трубка до стопы) ──────────────────────────────────────────────
    rod(f"{tag}_shin", knee_pos, foot_pos, THIGH_R, mat_petg, c_legs)

    # ── стопа ─────────────────────────────────────────────────────────────────
    sphere(f"{tag}_foot", foot_pos, FD/2, mat_tpu, c_legs)


# ══════════════════════════════════════════════════════════════════════════════
# РАЗМЕРНЫЕ ПОДПИСИ
# ══════════════════════════════════════════════════════════════════════════════
label_s = 0.0045
dims_info = [
    ("dim_BL",  f"Body L={P['body']['length']} mm",  (-BL/2, -BW/2 - 0.025, body_z + BH/2 + 0.005)),
    ("dim_BW",  f"Body W={P['body']['width']} mm",   ( BL/2 + 0.005, 0, body_z + BH/2 + 0.005)),
    ("dim_BH",  f"Body H={P['body']['height']} mm",  ( BL/2 + 0.005, BW/2 + 0.015, body_z)),
    ("dim_UL",  f"Thigh={P['leg']['upper_length']} mm", (SL/2 + 0.06, SW/2, (HIP_Z + HIP_Z-UL)/2)),
    ("dim_LL",  f"Shin={P['leg']['lower_length']} mm",  (SL/2 + 0.06, SW/2, HIP_Z - UL - LL/2)),
    ("dim_ST",  f"Back H={P['stance']['back_height_from_floor']} mm", (0, -BW/2-0.04, BACK_H/2)),
]
for n, txt, loc in dims_info:
    text3d(n, txt, loc, label_s, c_labels)


# ══════════════════════════════════════════════════════════════════════════════
# СОХРАНЕНИЕ .blend
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print(f"[NeuroPaw] Saved: {BLEND_OUT}")


# ══════════════════════════════════════════════════════════════════════════════
# ЭКСПОРТ STL
# ══════════════════════════════════════════════════════════════════════════════
def export_stl(keyword, filename):
    bpy.ops.object.select_all(action='DESELECT')
    found = False
    for obj in bpy.data.objects:
        if keyword.lower() in obj.name.lower():
            obj.select_set(True); found = True
    if not found:
        print(f"[NeuroPaw] STL skip (not found): {keyword}")
        return
    path = os.path.join(MESHES, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"[NeuroPaw] STL: {path}")

export_stl("body_main",   "body.stl")
export_stl("_thigh",      "thigh.stl")
export_stl("_shin",       "shin.stl")
export_stl("_foot",       "foot.stl")
export_stl("_servo",      "servo_mg996r.stl")


# ══════════════════════════════════════════════════════════════════════════════
# РЕНДЕРЫ
# ══════════════════════════════════════════════════════════════════════════════
scene = bpy.context.scene
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# Освещение
bpy.ops.object.light_add(type='SUN', location=(1.5, -1.5, 3))
sun = bpy.context.active_object; sun.data.energy = 4
link(sun, c_body)
bpy.ops.object.light_add(type='AREA', location=(-1, 1, 2))
area = bpy.context.active_object; area.data.energy = 400; area.data.size = 0.8
link(area, c_body)

scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.88, 0.88, 0.92, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8

scene.render.engine = 'CYCLES'
scene.cycles.samples = 96

# Центр сцены (середина тела по высоте)
focus_z = BACK_H / 2   # ~0.110 м

def render_view(name, cam_loc, cam_rot_deg):
    if "Camera" not in bpy.data.objects:
        bpy.ops.object.camera_add()
        cam = bpy.context.active_object
        link(cam, c_body)
    else:
        cam = bpy.data.objects["Camera"]

    cam.location = cam_loc
    cam.rotation_euler = [math.radians(r) for r in cam_rot_deg]
    cam.data.lens = 35      # мм — стандартный объектив, без перспективных искажений
    scene.camera = cam
    scene.render.filepath = os.path.join(RENDERS, name + ".png")
    bpy.ops.render.render(write_still=True)
    print(f"[NeuroPaw] Render: {name}.png")


# Расстояния подобраны так, чтобы вся собака попадала в кадр
render_view("side",
            (0.0, -0.70, focus_z),
            (90, 0, 0))

render_view("top",
            (0.0, 0.0, 0.65),
            (0, 0, 0))

render_view("front",
            (0.60, 0.0, focus_z),
            (90, 0, 90))

render_view("isometric",
            (0.55, -0.55, 0.45),
            (60, 0, 45))


# ══════════════════════════════════════════════════════════════════════════════
# ТАБЛИЦА ВЕСОВ И ПРОВЕРКА СЕРВ
# ══════════════════════════════════════════════════════════════════════════════
PETG_D = P["materials"]["petg_density_g_cm3"]
INF    = P["materials"]["petg_infill_percent"] / 100.0

def petg_g(l, w, h):   # мм → г
    return (l/10) * (w/10) * (h/10) * INF * PETG_D

parts_petg = {
    "Корпус (shell, 5мм стенки)":    petg_g(260, 110, 60) * 0.30,  # только стенки
    "Бёдра PETG-трубки × 4":         petg_g(14, 14, 110) * 4,
    "Голени PETG-трубки × 4":        petg_g(14, 14, 120) * 4,
    "Кронштейны плеча × 4":          petg_g(13, 20, 8) * 4,
}
tpu_g = 1.21 * (4/3)*math.pi*(10/10)**3 * 4    # 4 шара r=1cm

servo_g   = P["servo_mg996r"]["weight_g"] * 12
bat_g     = P["electronics"]["battery_2s_5000mah"]["weight_g"]
elec_g    = 150

petg_total = sum(parts_petg.values())
total_g    = petg_total + tpu_g + servo_g + bat_g + elec_g

# Нагрузка на бедренную серву: момент = (total_mass/4) × lever_hip
# rычаг — расстояние от оси бедра до проекции ЦМ на горизонталь
lever_hip_cm = (UL * math.cos(HIP_ANGLE)) * 100   # вертикальная проекция → рычаг плеча
load_hip_kgcm = (total_g/1000 / 4) * lever_hip_cm

# Нагрузка на коленную серву: голень + стопа
mass_shin_g = parts_petg["Голени PETG-трубки × 4"]/4 + tpu_g/4
lever_shin_cm = (LL / 2) * 100
load_knee_kgcm = (mass_shin_g/1000) * lever_shin_cm

torque_nom = P["servo_mg996r"]["torque_kgcm_at_6v"]
hip_pct  = load_hip_kgcm  / torque_nom * 100
knee_pct = load_knee_kgcm / torque_nom * 100

# Угол колена (между бедром и голенью)
thigh_dir = (math.sin(HIP_ANGLE), 0, -math.cos(HIP_ANGLE))
_, foot_pos0, _, sdx, sdz = leg_geometry(0, 0, +1)
shin_len = math.sqrt(sdx**2 + sdz**2)
shin_dir = (sdx/shin_len, 0, sdz/shin_len)
dot = thigh_dir[0]*shin_dir[0] + thigh_dir[2]*shin_dir[2]
dot = max(-1.0, min(1.0, dot))
knee_angle_deg = math.degrees(math.acos(dot))

report = f"""
╔══════════════════════════════════════════════════════════════╗
║            NeuroPaw — Таблица весов и нагрузки серв          ║
╚══════════════════════════════════════════════════════════════╝

── Геометрия стойки ──────────────────────────────────────────
  Высота спины от пола:             {BACK_H*1000:.0f} мм
  Центр корпуса от пола:            {body_z*1000:.0f} мм
  Высота шарнира бедра от пола:     {HIP_Z*1000:.0f} мм
  Угол наклона бедра от вертикали:  {math.degrees(HIP_ANGLE):.0f}°
  Угол в колене:                    {knee_angle_deg:.0f}°
  Позиция стопы (FL) X от плеча:   {foot_pos0[0]*1000:+.1f} мм

── Детали из PETG (заполнение {int(INF*100)}%) ─────────────────────────────
"""
for k, v in parts_petg.items():
    report += f"  {k:<40s} {v:6.1f} г\n"
report += f"""  Стопы TPU × 4:                           {tpu_g:6.1f} г
  ─────────────────────────────────────────────────────
  ИТОГО пластик:                           {petg_total + tpu_g:6.1f} г

── Прочие компоненты ─────────────────────────────────────────
  Сервы MG996R × 12:                       {servo_g:6.0f} г
  Батарея 2S 5000 мА·ч:                    {bat_g:6.0f} г
  Электроника + провода (оценка):          {elec_g:6.0f} г

  ══ ИТОГО:  {total_g:.0f} г ({total_g/1000:.2f} кг) ══

── Положение центра масс (оценка) ───────────────────────────
  X: ~0 мм  |  Y: ~0 мм  |  Z: ~{body_z*1000-10:.0f} мм от пола

── Проверка нагрузки MG996R (номинал {torque_nom} кг·см при 6В) ─────────
  Бедро:  ~{load_hip_kgcm:.2f} кг·см  → {hip_pct:.0f}% от номинала
  Колено: ~{load_knee_kgcm:.2f} кг·см  → {knee_pct:.0f}% от номинала

  Вывод: {'✅ Запас по моменту достаточный' if hip_pct < 80 else '⚠️  Нагрузка высокая!'}
  При общем весе {total_g:.0f} г бедренные сервы нагружены примерно
  на {hip_pct:.0f}% — статическая стойка без проблем; динамика (ходьба)
  добавит ещё 1.5–2× нагрузку.
"""
print(report)
with open(os.path.join(BASE_DIR, "weight_report.txt"), "w", encoding="utf-8") as f:
    f.write(report)

print("[NeuroPaw] DONE. Жду вашего утверждения перед экспортом MJCF.")
