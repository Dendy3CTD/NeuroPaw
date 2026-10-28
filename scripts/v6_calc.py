"""
NeuroPaw — v6_calc.py
Расчёты по фактической модели robodog_v6.blend: масса (PETG по объёму и площади),
центр масс, массы и инерции звеньев, моменты 20 суставов, токи, время работы.
Файл не сохраняет (маркер центра масс ставит scripts/v6_mark_com.py).
Запуск: blender --background robodog_v6.blend --python scripts/v6_calc.py
→ docs/servo_map.md, docs/engineering.md, docs/power.md, docs/sim_params.md, docs/calc_v6.json
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v6lib import checks, rig  # noqa: E402
from v6lib.layout import (BASE, KN, LEGS, N, P, SERVOS, SH_Y, STAND_HIP, STAND_KNEE,  # noqa: E402
                          stand_pose)
import v6_knee_linkage as KL  # noqa: E402
import v6_knee_spring as KS  # noqa: E402

checks.relink()
ARM = rig.ARM
G = 9.81
RHO = {"PETG": 1.27e-3, "TPU": 1.21e-3}          # г/мм³
INFILL, PERIM = P["print"]["infill"], P["print"]["perimeter_mm"]

METAL_G = {"knee_horn": 6, "knee_rod": 6, "knee_lever": 5}   # качалка 25T Al, тяга + 2 шаровых, рычаг
WIRE_G_PER_M = {"CAN_bus_cable": 4, "Power_head_harness": 28, "Sensor_I2C_sonar_cable": 6,
                "Camera_FPC_21mm": 2, "OTG_cable_10cm": 0, "OTG_5V_backup_wire": 3}       # OTG — масса в штекере/гнезде
M5 = 5.6                                                         # болт M5 × 25–30 + гайка, г
EXTRA = [("Жгуты сервоприводов (удлинители, ~0.25 м × 20)", 30, "Root"),
         ("Силовые провода AWG16 (батарея → UBEC, через позвоночник)", 40, "Root"),
         *[(f"Оси M5 ноги {lg} (отведение, бедро, колено)", 3 * M5, N[n0]) for lg, (_, _, n0) in LEGS.items()],
         ("Оси M5 позвоночника (2)", 2 * M5, N[14]), ("Ось M5 наклона шеи", M5, N[16]),
         ("Крепёж M3/M2.5 + термовставки (~140 шт.)", 70, None)]


def world_pts(o):
    return [o.matrix_world @ v.co * 1000 for v in o.data.vertices]


def surf(o):
    """Площадь (мм²), объём (мм³) и центр поверхности (мир, мм) меша без модификаторов."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(Matrix.Scale(1000, 4))
    area = sum(f.calc_area() for f in bm.faces)
    vol = abs(bm.calc_volume(signed=True))
    c = Vector()
    for f in bm.faces:
        c += f.calc_center_median() * f.calc_area()
    bm.free()
    c = o.matrix_world @ (c / max(area, 1e-9) / 1000) * 1000
    return area, vol, c


def classify(o):
    """→ (группа, масса г, центр мм)."""
    if "servo_no" in o:
        return "Сервоприводы", P["servos"][o["servo_type"]]["mass_g"], Vector(sum(world_pts(o), Vector()) / len(o.data.vertices))
    if o.get("bearing"):
        return "Подшипники", P["bearings"][o["bearing"]]["mass_g"], o.matrix_world.translation * 1000
    if "mass_g" in o:
        return o.get("group", "Электроника"), o["mass_g"], Vector(sum(world_pts(o), Vector()) / len(o.data.vertices))
    for k, g in METAL_G.items():
        if o.name.endswith(k):
            return "Качалки, тяги, рычаги", g, Vector(sum(world_pts(o), Vector()) / len(o.data.vertices))
    if o.name in WIRE_G_PER_M:
        pts = world_pts(o)
        length = sum((b - a).length for a, b in zip(pts[::8], pts[8::8])) / 1000
        return "Провода", WIRE_G_PER_M[o.name] * length, Vector(sum(pts, Vector()) / len(pts))
    area, vol, c = surf(o)
    mat = "TPU" if o.name.endswith(("_foot", "_TPU")) else "PETG"
    shell = min(vol, area * PERIM)
    return f"Печать {mat}", RHO[mat] * (shell + INFILL * max(0.0, vol - area * PERIM)), c


def collect():
    parts = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.name == "Floor" or o.name not in rig.LINK:
            continue
        grp, g, c = classify(o)
        parts.append({"name": o.name, "group": grp, "g": g, "c": c, "link": rig.LINK[o.name]})
    printed = sum(p["g"] for p in parts if p["group"].startswith("Печать"))
    for name, g, link in EXTRA:
        if link is None:      # крепёж — пропорционально печатным деталям
            for p in [p for p in parts if p["group"].startswith("Печать")]:
                p["g"] *= 1 + g / printed
            parts.append({"name": name, "group": "Крепёж (распределён по деталям)", "g": 0.0,
                          "c": Vector(), "link": "Root", "info_g": g})
        else:
            c = ARM.matrix_world @ ARM.data.bones[link].head_local * 1000
            grp = ("Оси M5 (болты + гайки)" if name.startswith("Оси") else
                   "Пружины колена" if name.startswith("Пружина") else "Провода")
            parts.append({"name": name, "group": grp, "g": g, "c": c, "link": link})
    return parts


def subtree(bone):
    names = {bone} | {b.name for b in ARM.data.bones[bone].children_recursive}
    return names


def com(parts, links=None):
    sel = [p for p in parts if links is None or p["link"] in links or
           (p["link"] == "CABLE" and links is None)]
    m = sum(p["g"] for p in sel)
    return m, (sum((p["c"] * p["g"] for p in sel), Vector()) / m if m else Vector())


# ── 1. масса и центр масс в стойке ────────────────────────────────────────────
rig.pose(stand_pose())
ARM.location = (0, 0, 0)
bpy.context.view_layer.update()
parts = collect()
M_TOT, C_TOT = com(parts)
mg_kg = M_TOT / 1000
groups = {}
for p in parts:
    groups[p["group"]] = groups.get(p["group"], 0) + p["g"] + p.get("info_g", 0) * 0
fasten_g = next(p["info_g"] for p in parts if "info_g" in p)


def link_mass(bones):
    return com(parts, bones)


# ── 2. моменты суставов ───────────────────────────────────────────────────────
FOOT_Y = P["leg"]["foot_y"]
W3 = 0.51            # доля веса на самой нагруженной ноге при стойке на трёх
knee_pts = KL.evaluate(KN["r1"], KN["r2"], math.radians(KN["beta_deg"]), KN["rod_L"], KN["servo_u"],
                       KN["kappa_min"], KN["kappa_max"], 1.0)


def knee_ratio(k):
    return min(knee_pts, key=lambda p: abs(p[0] - k))[3]


def head_after_pitch(deg):
    """Плечо (см) центра масс головы+шеи относительно оси наклона шеи после поворота."""
    m, c = link_mass(subtree(N[16]))
    ax = ARM.matrix_world @ ARM.data.bones[N[16]].head_local * 1000
    d = c - ax
    a = math.radians(deg)
    dx = d.x * math.cos(a) + d.z * math.sin(a)
    return m / 1000, abs(dx) / 10


req = {}
lever_stand = KL.knee_lever(175, 0)[0] / 10
kap_st = -STAND_KNEE
for leg, (xs, ys, n0) in LEGS.items():
    req[n0] = (W3 * mg_kg * (FOOT_Y - SH_Y) / 10, "3 ноги: 51 % веса × смещение стопы от оси отведения")
    req[n0 + 1] = (max(W3 * mg_kg * 4.0, 0.25 * mg_kg * 1.3 * 3.3),
                   "3 ноги, стопа вынесена на 40 мм (вставание: 0.25·m·1.3 × 33 мм — меньше)")
    t_trot = 0.5 * mg_kg * 1.3 * lever_stand / knee_ratio(kap_st)
    req[n0 + 2] = (t_trot, f"рысь ×1.3: момент в колене {0.5 * mg_kg * 1.3 * lever_stand:.1f} / передача {knee_ratio(kap_st):.2f}")

# 14 pitch позвоночника: изгиб в узле при стойке, ×1.5 на шаг
front = subtree(N[13])
x_ax = (ARM.matrix_world @ ARM.data.bones[N[14]].head_local * 1000).x
R_f = M_TOT * (C_TOT.x + 110) / 220
mom = (R_f * (110 - x_ax) - sum(p["g"] * (p["c"].x - x_ax) for p in parts if p["link"] in front)) / 1000 / 10
req[14] = (abs(mom) * 1.5, f"изгиб в узле при стойке {abs(mom):.2f} кг·см × 1.5 (шаг)")
req[13] = (0.15 * mg_kg * 8.6, "рысь: боковые силы передних стоп 15 % веса × 86 мм до оси")
m_t, c_t = link_mass(subtree(N[15]))
ax_t = ARM.matrix_world @ ARM.data.bones[N[15]].head_local * 1000
req[15] = (m_t / 1000 * abs(c_t.x - ax_t.x) / 10 * 1.5, "хвост горизонтально × 1.5 (размах)")
mh, arm_h = head_after_pitch(45)
req[16] = (mh * arm_h + 0.05 * (arm_h + 6), f"голова+шея {mh * 1000:.0f} г, наклон +45°, + игрушка 50 г")
m_hy, c_hy = link_mass(subtree(N[17]))
ax_y = ARM.matrix_world @ ARM.data.bones[N[17]].head_local * 1000
off = (c_hy - ax_y).xy.length / 10
req[17] = (m_hy / 1000 * off * 0.71 + 0.1,
           "шея наклонена 45°: тяжесть головы относительно оси поворота + разгон")
m_j, c_j = link_mass(subtree(N[18]))
ax_j = ARM.matrix_world @ ARM.data.bones[N[18]].head_local * 1000
req[18] = (m_j / 1000 * abs(c_j.x - ax_j.x) / 10 + 0.05 * 3.5 + 0.25,
           "челюсть + игрушка 50 г на 35 мм + удержание (INA226 ограничивает)")
for no in (19, 20):
    m_e, c_e = link_mass(subtree(N[no]))
    ax_e = ARM.matrix_world @ ARM.data.bones[N[no]].head_local * 1000
    req[no] = (m_e / 1000 * (c_e - ax_e).length / 10 * 2, "ухо горизонтально × 2 (быстрый взмах)")

# ── 3. токи ───────────────────────────────────────────────────────────────────
branch = {"UBEC_F": [], "UBEC_R": []}
for no, name, joint, kind, rr, board, ch, power in SERVOS:
    branch["UBEC_F" if power.startswith("UBEC_F") else "UBEC_R"].append((no, kind))


def amps(lst, leg_share, other_share):
    return sum(P["servos"][k]["stall_a"] * (leg_share if n <= 12 else other_share) for n, k in lst)


cur = {}
for b, lst in branch.items():
    cur[b] = {"stall": amps(lst, 1, 1), "peak": amps(lst, 0.7, 0.3),
              "walk": sum(0.5 if n <= 12 else 0.15 for n, k in lst),
              "stand": sum(0.25 if n <= 12 else 0.05 for n, k in lst)}
E = P["electronics"]
logic_peak = sum(v.get("i5_peak_a", 0) for v in E.values())
logic_avg = sum(v.get("i5_avg_a", 0) for v in E.values())
BAT = P["power"]["battery"]
wh = BAT["voltage_nom"] * BAT["capacity_mah"] / 1000
usable = wh * 0.8
V_LOAD = 6.8          # напряжение пакета под нагрузкой


def batt(i_servo, i_logic):
    w = i_servo * 6 / 0.9 + i_logic * 5 / 0.9
    return w / V_LOAD, w, usable / w * 60


# ── 4. звенья для MuJoCo (в покое, оси звена = мировые оси в позе покоя) ───────
rig.pose({})
for c in [c for pb in ARM.pose.bones for c in pb.constraints if c.type == 'LIMIT_ROTATION']:
    c.mute = True
bpy.context.view_layer.update()
parts_rest = collect()
links = {}
for p in parts_rest:
    lk = p["link"]
    if lk == "CABLE" or p["g"] <= 0:
        continue
    if lk.startswith("MCH_"):
        lk = rig.ARM.data.bones[lk].parent.name
    links.setdefault(lk, []).append(p)
link_rows = []
for lk, ps in links.items():
    m = sum(p["g"] for p in ps)
    c = sum((p["c"] * p["g"] for p in ps), Vector()) / m
    head = ARM.data.bones[lk].head_local * 1000
    I = [[0.0] * 3 for _ in range(3)]
    for p in ps:
        r = (p["c"] - c) / 1000
        mk = p["g"] / 1000
        for i in range(3):
            for j in range(3):
                I[i][j] += mk * ((r.length_squared if i == j else 0) - r[i] * r[j])
    link_rows.append((lk, m, c - head, I))

# ── 5. документы ──────────────────────────────────────────────────────────────
docs = os.path.join(BASE, "docs")
servo_rows, low = [], []
for no, name, joint, kind, rr, board, ch, power in SERVOS:
    need, note = req[no]
    have = P["servos"][kind]["torque_kgcm"]
    k = have / need if need else 99
    flag = " ⚠" if k < 1.5 else ""
    if k < 1.5:
        low.append(name)
    rng_txt = f"{rr[0]}…{rr[1]}°" if no not in (3, 6, 9, 12) else f"κ {-rr[1]}…{-rr[0]}°"
    servo_rows.append(f"| {no:02d} | `{name}` | {joint} | {kind} | {board} | {ch} | {power} | "
                      f"{rng_txt} | {need:.2f} | {have:.1f} | **{k:.1f}**{flag} | {note} |")
with open(os.path.join(docs, "servo_map.md"), "w") as f:
    f.write("\n".join([
        "# Карта сервоприводов NeuroPaw v6", "",
        "Источник: `params.json[\"servo_table\"]`, расчёт — `scripts/v6_calc.py` по модели "
        f"`robodog_v6.blend` (масса {M_TOT / 1000:.2f} кг). Момент — при 6 В.",
        "Ход колена дан как сгибание κ (0 = прямая нога); кость колена: φ = −κ. "
        "Колено через тягу: «нужно» — момент на валу сервы (уже делённый на передачу).", "",
        "| № | Объект / кость | Сустав | Тип | Плата | Канал | Питание | Ход | Нужно, кг·см | Есть | Запас | Худшая поза |",
        "|---|---|---|---|---|---|---|---|---:|---:|---:|---|"] + servo_rows + [
        "", "⚠ — запас ниже 1.5." if low else "Все суставы с запасом ≥ 1.5.", ""]))

lines = ["# Инженерный расчёт NeuroPaw v6", "",
         "Источник: `scripts/v6_calc.py` по модели `robodog_v6.blend`, поза «стоит».",
         f"Печать: PETG {RHO['PETG'] * 1000:.2f} г/см³, стенки {PERIM} мм сплошные + заполнение "
         f"{INFILL:.0%}; TPU 95A для стоп. Перекрытия примитивов внутри детали считаются дважды "
         "(завышение ≈ 5–10 %).", "",
         f"## Масса: **{M_TOT / 1000:.2f} кг** (цель ~2.3 кг)", "",
         "| Группа | г |", "|---|---:|"]
for g, v in sorted(groups.items(), key=lambda t: -t[1]):
    lines.append(f"| {g} | {v:.0f} |")
lines.append(f"| в т. ч. крепёж, распределён по печатным деталям | {fasten_g:.0f} |")
lines += ["", f"## Центр масс (стойка): X = **{C_TOT.x:+.1f}**, Y = {C_TOT.y:+.1f}, Z = {C_TOT.z:.1f} мм",
          "X = 0 — середина между осями бёдер (±110 мм), + к голове. В сцене маркер `CoM_marker`.", "",
          "| Узел | Масса, г | X ЦМ, мм |", "|---|---:|---:|"]
for title, bones in (("Голова + шея (16→)", subtree(N[16])), ("Передняя секция без ног", front - subtree(N[16]) - set().union(*[subtree(N[n]) for n in (1, 4)])),
                     ("Задняя секция без ног и хвоста", {"Root", N[14]}), ("Нога (одна, FL)", subtree(N[1]))):
    m, c = link_mass(bones)
    lines.append(f"| {title} | {m:.0f} | {c.x:+.0f} |")
lines += ["", "## Запас по моменту", "", "Полная таблица — `docs/servo_map.md`.",
          ("Ниже 1.5: " + ", ".join(low)) if low else "Все 20 суставов с запасом ≥ 1.5.",
          "", "## Колено", "", "`docs/knee_linkage.md`: передача "
          f"{KN['ratio_stance']:.2f} в стойке, ход κ {KN['kappa_min']}…{KN['kappa_max']}°."]
with open(os.path.join(docs, "engineering.md"), "w") as f:
    f.write("\n".join(lines) + "\n")

pw = ["# Питание NeuroPaw v6", "", "Источник: `params.json[\"power\"]`, `scripts/v6_calc.py`.", "",
      "## Схема", "", "```",
      "2S2P Molicel P28A (7.2 В, 5600 мА·ч, 50 А) + BMS 2S 40 А",
      "  └─ предохранитель 40 А ─ XT60 loop-key (главный выключатель); напряжение — делитель 100к/33к → GPIO36 «Тела»",
      "      ├─ предохр. 25 А ─ UBEC-П 6 В 20 А ─ MOSFET ─ передние ноги 01–06",
      "      │                                    └ MOSFET ─ (шея) 16, 17, челюсть 18 через INA226, уши 19, 20",
      "      ├─ предохр. 25 А ─ UBEC-З 6 В 20 А ─ MOSFET ─ задние ноги 07–12, позвоночник 13, 14, хвост 15",
      "      └─ предохр. 5 А ─ DC-DC 5 В 5 А ─ ESP32 + 2 × ESP32-S3 + ESP32-C3, экраны, HC-SR04 (≤ 50 %), звук, датчики",
      "Земля — звездой на минусе батареи. 2200 мкФ Low-ESR: у PCA9685, на выходе UBEC-П, в голове.",
      "Мягкий старт: OE PCA9685 подтянут к 3.3 В (выходы выключены при загрузке),",
      "  «Тело» включает ветки MOSFET по очереди с паузой ~200 мс.", "```", "",
      "## Токи сервоприводов (6 В)", "",
      "| Ветка | Сервы | Все в stall, А | Пик (вставание), А | Ходьба, А | Стоит, А | UBEC |",
      "|---|---|---:|---:|---:|---:|---|"]
for b, lst in branch.items():
    c = cur[b]
    ok = "✓" if c["peak"] < 20 else "⚠"
    pw.append(f"| {b} | {', '.join(f'{n:02d}' for n, k in lst)} | {c['stall']:.1f} | {c['peak']:.1f} | "
              f"{c['walk']:.1f} | {c['stand']:.1f} | 20 А {ok} |")
tot = {k: cur['UBEC_F'][k] + cur['UBEC_R'][k] for k in ("stall", "peak", "walk", "stand")}
pw += ["", "Пик — ноги 70 % stall, остальные 30 %. «Все в stall» — заклинивание всех серв ветки одновременно: "
       "UBEC уходит в защиту раньше, чем сгорит предохранитель 25 А.", "",
       "## Логика 5 В", "",
       f"Пик {logic_peak:.2f} А, среднее {logic_avg:.2f} А — DC-DC 5 А с запасом.", "",
       "## Батарея", "",
       f"{BAT['config']} {BAT['cells']}: {wh:.1f} Вт·ч, используем 80 % = {usable:.1f} Вт·ч. "
       f"Ток пакета считаем при {V_LOAD} В под нагрузкой, КПД преобразователей 90 %.", "",
       "| Режим | Сервы, А | Логика, А | Мощность, Вт | Ток батареи, А | Время |", "|---|---:|---:|---:|---:|---:|"]
for mode, i_s, i_l in (("Пик (вставание)", tot["peak"], logic_peak), ("Все сервы в stall", tot["stall"], logic_peak),
                       ("Ходьба", tot["walk"], logic_avg), ("Стоит", tot["stand"], logic_avg),
                       ("Лежит, сервы без нагрузки", 0.2, logic_avg)):
    ia, w, t = batt(i_s, i_l)
    pw.append(f"| {mode} | {i_s:.1f} | {i_l:.2f} | {w:.0f} | {ia:.1f} | "
              + (f"{t:.0f} мин |" if "stall" not in mode and "Пик" not in mode else "— |"))
ia_stall = batt(tot["stall"], logic_peak)[0]
pw += ["", f"P28A: 25 А на ячейку → пакет 2P = 50 А. BMS 40 А и предохранитель 40 А: "
       f"пик вставания {batt(tot['peak'], logic_peak)[0]:.0f} А проходит; "
       f"одновременный stall всех серв ({ia_stall:.0f} А) — {'выше 40 А: сработает защита BMS' if ia_stall > 40 else 'в пределах'}."]
with open(os.path.join(docs, "power.md"), "w") as f:
    f.write("\n".join(pw) + "\n")

sp = ["# Параметры для MuJoCo (NeuroPaw v6)", "",
      "Источник: `scripts/v6_calc.py` по `robodog_v6.blend`. Система координат: X вперёд, Y влево, Z вверх; "
      "оси звена совпадают с мировыми в позе покоя (ноги прямые). ЦМ звена — от оси его сустава, мм. "
      "Инерция — относительно ЦМ звена, кг·м² (оценка по точечным массам деталей, без собственной "
      "инерции деталей — занижение у крупных деталей корпуса).", "",
      "## Приводы", "",
      "| Тип | Момент @6 В, Н·м | Скорость, рад/с | Люфт, ° | Мёртвая зона, мкс | Stall, А |",
      "|---|---:|---:|---:|---:|---:|"]
for k, s in P["servos"].items():
    sp.append(f"| {k} | {s['torque_kgcm'] * G / 100:.2f} | {math.radians(60) / s['speed_s60']:.1f} | "
              f"{s['backlash_deg']} | {s['deadband_us']} | {s['stall_a']} |")
sp += ["", "## Колено", "",
       f"Привод через четырёхзвенник: r1 {KN['r1']} мм, r2 {KN['r2']} мм, тяга {KN['rod_L']} мм. "
       f"Передача нелинейная, таблица κ → (угол сервы, передача) — `docs/knee_linkage.md`; "
       f"в стойке {KN['ratio_stance']:.2f}, на шаге ≥ {KN['ratio_min_walk']:.2f}. "
       f"Ход κ {KN['kappa_min']}…{KN['work_max_deg']:.0f}° (кость: {-KN['work_max_deg']:.0f}…{-KN['kappa_min']}°), "
       f"упор {KN['stop_deg']}°, мёртвая точка тяги {KN['toggle_deg']}°. "
       "В MuJoCo: joint колена с `gear` по таблице или `ctrlrange` сервы + tendon/таблица.", "",
       "## Звенья", "", "| Звено (кость) | Масса, г | ЦМ от оси, мм | Ixx | Iyy | Izz |", "|---|---:|---|---:|---:|---:|"]
for lk, m, c, I in sorted(link_rows, key=lambda r: r[0]):
    sp.append(f"| `{lk}` | {m:.1f} | ({c.x:+.1f}, {c.y:+.1f}, {c.z:+.1f}) | "
              f"{I[0][0]:.2e} | {I[1][1]:.2e} | {I[2][2]:.2e} |")
sp += ["", "## Оси суставов (поза покоя, мм)", "", "| Кость | Точка оси | Ось | Ход, ° |", "|---|---|---|---|"]
for no, name, *_ in SERVOS:
    b = ARM.data.bones[name]
    h = b.head_local * 1000
    ax = b.vector.normalized()
    rr = SERVOS[no - 1][4]
    sp.append(f"| `{name}` | ({h.x:.1f}, {h.y:.1f}, {h.z:.1f}) | ({ax.x:.0f}, {ax.y:.0f}, {ax.z:.0f}) | {rr[0]}…{rr[1]} |")
imu = []
for n in ("IMU_rear_MPU6050_0x68", "IMU_front_MPU6050_0x69"):
    o = bpy.data.objects[n]
    c = sum(world_pts(o), Vector()) / len(o.data.vertices)
    head = ARM.data.bones[rig.LINK[n]].head_local * 1000
    imu.append(f"| {n} | `{rig.LINK[n]}` | ({c.x:.1f}, {c.y:.1f}, {c.z:.1f}) | ({(c - head).x:+.1f}, {(c - head).y:+.1f}, {(c - head).z:+.1f}) |")
sp += ["", "## IMU", "", "| IMU | Звено | Положение (мир, покой), мм | От оси звена, мм |", "|---|---|---|---|"] + imu
sp += ["", f"Масса робота {M_TOT / 1000:.3f} кг, ЦМ в стойке ({C_TOT.x:+.1f}, {C_TOT.y:+.1f}, {C_TOT.z:.1f}) мм. "
       f"Стойка: бедро {STAND_HIP:.1f}°, колено {STAND_KNEE:.1f}° (φ)."]
with open(os.path.join(docs, "sim_params.md"), "w") as f:
    f.write("\n".join(sp) + "\n")

# ── 6. пружина колена, устойчивость, расход пластика ──────────────────────────
def on_floor(rot_deg):
    ARM.rotation_euler = (0, math.radians(rot_deg), 0)
    ARM.location.z = 0
    bpy.context.view_layer.update()
    feet = checks.feet()
    ARM.location.z -= min(feet.values()) * 0.001
    bpy.context.view_layer.update()


def support_margin():
    """ЦМ над многоугольником стоп: мин. расстояние до края, мм (+ внутри, − снаружи)."""
    ps = collect()
    _, c = com(ps)
    pts = []
    for lg in ("FL", "FR", "BR", "BL"):
        o = bpy.data.objects[f"{lg}_foot"]
        v = sum((o.matrix_world @ q.co for q in o.data.vertices), Vector()) / len(o.data.vertices) * 1000
        pts.append(v.xy)
    d = []
    for i in range(4):
        a_, b_ = pts[i], pts[(i + 1) % 4]
        e = (b_ - a_).normalized()
        nrm = Vector((-e.y, e.x))
        d.append((c.xy - a_).dot(nrm))
    if sum(d) < 0:
        d = [-x for x in d]
    return min(d), c


poses_js = json.load(open(os.path.join(BASE, "docs", "poses_v6.json")))
stab = {}
for name, front_, rear_, extra_ in (("стоит", (STAND_HIP, -STAND_KNEE), (STAND_HIP, -STAND_KNEE), {}),
                                     ("сидит", (poses_js["sit"]["front_hip_deg"], 70.0), (90.0, 128.0),
                                      {N[14]: poses_js["sit"]["spine_deg"], N[16]: -20.0})):
    ang = {}
    for lg, (xs, ys, n0) in LEGS.items():
        th, ka = front_ if lg in ("FL", "FR") else rear_
        ang[N[n0 + 1]], ang[N[n0 + 2]] = th, -ka
    ang.update(extra_)
    rig.pose(ang)
    on_floor(0.0 if name == "стоит" else -poses_js["sit"]["tilt_deg"])
    stab[name] = support_margin()


def pose_world(front_, rear_, extra_, tilt):
    ang = {}
    for lg, (xs, ys, n0) in LEGS.items():
        th, ka = front_ if lg in ("FL", "FR") else rear_
        ang[N[n0 + 1]], ang[N[n0 + 2]] = th, -ka
    ang.update(extra_)
    rig.pose(ang)
    on_floor(tilt)


def knee_load(leg, dyn=1.0, share=None):
    """Момент в колене от реакции пола (кг·см, + сгибает): доля веса × плечо по X колено–стопа."""
    kn = ARM.matrix_world @ ARM.pose.bones[N[LEGS[leg][2] + 2]].head * 1000
    o = bpy.data.objects[f"{leg}_foot"]
    ft = min((o.matrix_world @ q.co * 1000 for q in o.data.vertices), key=lambda v: v.z)
    if share is None:
        _, c = com(collect())
        def fx(g):
            ob = bpy.data.objects[f"{g}_foot"]
            return sum((ob.matrix_world @ q.co).x for q in ob.data.vertices) / len(ob.data.vertices) * 1000
        xf, xr = (fx("FL") + fx("FR")) / 2, (fx("BL") + fx("BR")) / 2
        fr = (c.x - xr) / (xf - xr)
        share = (fr if leg in ("FL", "FR") else 1 - fr) / 2
    return share * mg_kg * dyn * abs(kn.x - ft.x) / 10, share


ST = (STAND_HIP, -STAND_KNEE)
SIT_F = (poses_js["sit"]["front_hip_deg"], 70.0)
SIT = {N[14]: poses_js["sit"]["spine_deg"], N[16]: -20.0}
loads = []
for name, fr_, re_, ex_, tilt, leg, dyn, share in (
        ("стоит", ST, ST, {}, 0.0, "FL", 1.0, 0.25),
        ("рысь, 2 ноги ×1.3", ST, ST, {}, 0.0, "FL", 1.3, 0.5),
        ("высокая стойка", (30.0, 65.0), (30.0, 65.0), {}, 0.0, "FL", 1.0, 0.25),
        ("встаёт (середина) ×1.3", (75.0, 115.0), (75.0, 115.0), {}, 0.0, "FL", 1.3, 0.25),
        ("лежит", (90.0, 128.0), (90.0, 128.0), {}, 0.0, "FL", 1.0, 0.25),
        ("встаёт из «лежит» ×1.3", (90.0, 128.0), (90.0, 128.0), {}, 0.0, "FL", 1.3, 0.25),
        ("сидит — задняя нога", SIT_F, (90.0, 128.0), SIT, -poses_js["sit"]["tilt_deg"], "BL", 1.0, None),
        ("сидит — передняя нога", SIT_F, (90.0, 128.0), SIT, -poses_js["sit"]["tilt_deg"], "FL", 1.0, None)):
    pose_world(fr_, re_, ex_, tilt)
    t, sh = knee_load(leg, dyn, share)
    kap = (fr_ if leg == "FL" else re_)[1]
    loads.append((name, kap, t, 0.0, sh))
lev_w, kap_w = KL.knee_lever(175, 40)
loads.insert(2, ("шаг, 3 ноги, стопа +40 мм", kap_w, W3 * mg_kg * lev_w / 10, 0.0, W3))
m_sh, c_sh = link_mass(subtree(N[3]))
kn0 = ARM.data.bones[N[3]].head_local * 1000
t_swing = m_sh / 1000 * (c_sh - kn0).length / 10 + 0.3          # тяжесть голени + разгон (~200 рад/с²)
for kap in range(65, 121, 5):
    loads.append((f"перенос ноги, κ {kap}°", float(kap), 0.0, t_swing, 0.0))
L4 = [(n, k, t, sp) for n, k, t, sp, _ in loads]
SPR = KS.optimize(L4, knee_ratio, 128.0)
no_spr = KS.margins(L4, knee_ratio, 0.0, 0)
with_spr = KS.margins(L4, knee_ratio, SPR["k"], SPR["pre"])
worst = min(with_spr, key=lambda r: r[2])
ARM.rotation_euler = (0, 0, 0)
ARM.location.z = 0
petg = groups.get("Печать PETG", 0)
petg_use = petg * 1.15 * 1.2 / 1000

eng = open(os.path.join(docs, "engineering.md")).read().rstrip("\n").split("\n")
eng += ["", "## Пружина колена (на всех 4 ногах)", "",
        "Помогает разгибать колено (держит вес); при сгибании и в переносе ноги серва работает против неё. "
        "Подбор — `scripts/v6_knee_spring.py`: максимум наименьшего запаса по всем позам, проволока в пределах "
        "0.6·Sut при κ 128°, витки не садятся на болт M5.", ""] + KS.describe(SPR, 128.0) + [
        "", "| Поза | κ, ° | Нагрузка в колене, кг·см | Пружина, кг·см | Передача | Запас без пружины | Запас с пружиной |",
        "|---|---:|---:|---:|---:|---:|---:|"]
for (n_, k_, t_, sp_, sh_), (_, _, m0), (_, _, m1) in zip(loads, no_spr, with_spr):
    eng.append(f"| {n_} | {k_:.0f} | {t_:.2f}{f' ± {sp_:.2f}' if sp_ else ''} | {KS.torque(SPR['k'], SPR['pre'], k_):.2f} | "
               f"{knee_ratio(k_):.2f} | {m0:.1f} | **{m1:.2f}** |")
eng += ["", f"Наименьший запас с пружиной **{worst[2]:.2f}** ({worst[0]}); без пружины — "
        f"{min(m for _, _, m in no_spr):.2f} ({min(no_spr, key=lambda r: r[2])[0]})."]
eng += ["", "## Устойчивость (ЦМ над опорой из четырёх стоп)", "",
        "| Поза | ЦМ X, мм | ЦМ Z, мм | До края опоры, мм |", "|---|---:|---:|---:|"]
eng += [f"| {k} | {c.x:+.0f} | {c.z:.0f} | **{m:+.0f}** |" for k, (m, c) in stab.items()]
eng += ["", "## Расход пластика", "",
        f"PETG в деталях {petg:.0f} г (с крепежом); +15 % поддержки/кайма, +20 % перепечатка нагруженных "
        f"деталей → **≈ {petg_use:.2f} кг** (в смете 2 кг).",
        f"TPU (стопы, губы, зубы) {groups.get('Печать TPU', 0):.0f} г — катушки 0.5 кг хватает с большим запасом."]
open(os.path.join(docs, "engineering.md"), "w").write("\n".join(eng) + "\n")
print(f"[calc] пружина: d {SPR['d']} OD {SPR['od']} n {SPR['n']} k {SPR['k']:.0f} Н·мм/рад, натяг {SPR['pre']}°")
for (n_, k_, *_), (_, _, m0), (_, _, m1) in zip(loads, no_spr, with_spr):
    print(f"[calc]   {n_}: κ {k_:.0f}, без {m0:.2f}, с пружиной {m1:.2f}")
P_SPR = {"wire_d_mm": SPR["d"], "od_mm": SPR["od"], "turns": SPR["n"], "k_nmm_rad": round(SPR["k"], 1),
         "preload_deg_at_65": SPR["pre"], "min_margin": round(worst[2], 2), "worst_pose": worst[0]}
spj = os.path.join(BASE, "params.json")
PJ = json.load(open(spj))
PJ["knee_spring"] = P_SPR
json.dump(PJ, open(spj, "w"), ensure_ascii=False, indent=2)
with open(os.path.join(docs, "sim_params.md"), "a") as f:
    kfree = 65.0 - SPR["pre"]
    f.write("\n".join(["", "## Пружина колена (пружинный элемент сустава)", "",
        f"Торсион на каждом колене: жёсткость **{SPR['k'] / 1000:.4f} Н·м/рад**, свободное положение при "
        f"κ = {kfree:.0f}° (натяг {SPR['pre']}° при κ 65°). Момент разгибает колено: τ = k·(κ − κ_free).",
        "", "```xml",
        f'<joint name="knee" ... stiffness="{SPR["k"] / 1000:.4f}" springref="{math.radians(-kfree):.4f}"/>',
        "```", "Кость колена φ = −κ, поэтому springref = −κ_free (рад). Демпфирование пружины не задаём.", ""]))
sm = os.path.join(docs, "servo_map.md")
rows = open(sm).read().split("\n")
for i, r in enumerate(rows):
    if r.startswith(("| 03 |", "| 06 |", "| 09 |", "| 12 |")):
        f_ = r.split("|")
        f_[9] = f" {11.0 / worst[2]:.2f} "
        f_[11] = f" **{worst[2]:.1f}** "
        f_[12] = f" с пружиной {SPR['d']} мм: худшая поза — {worst[0]} (все позы — engineering.md) "
        rows[i] = "|".join(f_)
open(sm, "w").write("\n".join(rows))
for k, (m, c) in stab.items():
    print(f"[calc] устойчивость {k}: ЦМ X {c.x:+.0f} Z {c.z:.0f}, до края опоры {m:+.0f} мм")
print(f"[calc] PETG {petg:.0f} г → расход ≈ {petg_use:.2f} кг")

json.dump({"mass_g": M_TOT, "com_mm": list(C_TOT), "groups": groups,
           "currents": cur, "logic": [logic_peak, logic_avg], "low_margin": low,
           "req": {k: v[0] for k, v in req.items()}},
          open(os.path.join(docs, "calc_v6.json"), "w"), ensure_ascii=False, indent=1)
print(f"[calc] масса {M_TOT / 1000:.3f} кг, ЦМ ({C_TOT.x:+.1f}, {C_TOT.y:+.1f}, {C_TOT.z:.1f})")
for g, v in sorted(groups.items(), key=lambda t: -t[1]):
    print(f"[calc]   {g}: {v:.0f} г")
print("[calc] запас < 1.5:", low or "нет")
for r in servo_rows:
    print("[calc] " + r)
for b in cur:
    print(f"[calc] {b}: {cur[b]}")
print(f"[calc] логика 5 В: пик {logic_peak:.2f} А, среднее {logic_avg:.2f} А")
