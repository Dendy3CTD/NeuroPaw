"""Ноги: отведение → бедро → колено; колено — четырёхзвенник (качалка → тяга → рычаг)."""
import math

from mathutils import Vector

from . import rig
from .geom import Mesh, col, frame, rng
from .layout import (AXIS_Z, BETA, BOSS_IN, CAP_Y, END, FOOT_R, HORN_A0, HX, KNEE_SERVO_D,
                     KNEE_STOP, KNEE_U, LEG_Y, LEGS, LINK_Y, LL, N, P, PLATE_IN, PLATE_OUT, R1, R2,
                     ROD_L, ROD_Y, SH_X, SH_Y, SHAFT_Y, UL, horn_expr)
from .parts import M, place_servo

C = "Structure/Legs"
HW_C = "Hardware/Bearings"


def bearing(name, kind, center, axis, link, mate):
    """Подшипник из params.bearings: обойма в звене link, внутреннее кольцо на оси звена mate.

    Посадочное отверстие в звене — Ø(D + 0.2). 51100 — упорный: две шайбы и сепаратор.
    """
    b = P["bearings"][kind]
    D, d, B = b["D"], b["d"], b["B"]
    m = Mesh().mat(M["steel"])
    if kind == "51100":
        a = Vector(axis).normalized()
        for k in (-1, 1):
            m.ring(Vector(center) + a * k * B / 3, axis, D / 2, d / 2 + 0.1, B / 3)
        m.mat(M["dark"]).ring(center, axis, D / 2 - 1.5, d / 2 + 1.5, B / 3)
    else:
        m.ring(center, axis, D / 2, d / 2, B)
        m.mat(M["tpu"]).ring(center, axis, D / 2 - D * 0.08, d / 2 + D * 0.08, B + 0.2)
    rig.make(name, m, col(HW_C), link, origin=center,
             props={"bearing": kind, "bearing_mate": mate, "seat_d_mm": b.get("seat_d", D + 0.2)})


def _bracket(leg, xs, ys, hx, hz, b_abd, b_body):
    m = Mesh().mat(M["accent"])
    m.ring((xs * (SH_X + 0.2 + (END + 1 - SH_X) / 2), ys * SH_Y, hz), (1, 0, 0), 7.4, 3.0,
           END + 1 - SH_X - 0.4)                                # ступица в 6802 стенки
    m.cyl((xs * (END + 2), ys * SH_Y, hz), (1, 0, 0), 11, 2)   # диск под качалку 25T
    m.box(rng(END + 3, END + 6.2, xs), rng(33, 58, ys), (hz - 12, hz + 16))
    m.box(rng(END + 3, END + 6.2, xs), rng(33, 104, ys), (hz + 16, hz + 41))
    m.box(rng(HX - 13, END + 6.2, xs), rng(94.3, 97.5, ys), (hz + 30.5, hz + 41))
    m.box(rng(HX + 10, END + 6.2, xs), rng(94.3, 97.5, ys), (hz + 16, hz + 41))
    # крышка на дне сервы бедра с осью Ø5 и перемычка к верхней планке
    m.box((hx - 12, hx + 12), rng(*CAP_Y, ys), (hz - 12, hz + 41))
    m.box((hx - 12, hx + 12), rng(CAP_Y[0], 97.5, ys), (hz + 37.5, hz + 41))
    m.mat(M["steel"]).cyl((hx, ys * (BOSS_IN[0] - 0.3 + CAP_Y[0]) / 2, hz), (0, 1, 0), 2.5,
                          CAP_Y[0] - BOSS_IN[0] + 0.3)
    # болт M5 по оси отведения из передней пластины в 625ZZ моста груди/кормы
    m.mat(M["steel"]).cyl((xs * (END + 9.6), ys * SH_Y, hz), (1, 0, 0), 2.5, 6.8, 20)
    rig.make(f"{leg}_shoulder_bracket", m, col(C), b_abd, bevel=1.2,
             props={"print_orientation": "торцевой пластиной на стол", "loaded": True})
    bearing(f"{leg}_bearing_abduction_625", "625ZZ",
            (xs * (END + 10.5), ys * SH_Y, hz), (1, 0, 0), b_body, b_abd)


def _knee_linkage(leg, xs, ys, hx, hz, b_hip, b_knee):
    sx, sz = hx + KNEE_U, hz - KNEE_SERVO_D
    h0 = (sx + R1 * math.cos(HORN_A0), sz + R1 * math.sin(HORN_A0))
    horn = f"MCH_{leg}_knee_horn"
    m = Mesh().mat(M["horn"])
    m.cyl((sx, ys * (SHAFT_Y + 4 + LINK_Y[1]) / 2, sz), (0, 1, 0), 3.5, LINK_Y[1] - SHAFT_Y - 4)
    m.stadium((sx, sz), h0, 7, 4, rng(*LINK_Y, ys))
    m.mat(M["steel"]).cyl((h0[0], ys * (LINK_Y[1] + ROD_Y) / 2, h0[1]), (0, 1, 0), 1.5,
                          ROD_Y - LINK_Y[1] + 1)
    rig.make(f"{leg}_knee_horn", m, col(C), horn, props={"part": "качалка 25T Al, r 15 мм"})

    kz = hz - UL
    t0 = (hx + R2 * math.cos(BETA), kz + R2 * math.sin(BETA))
    m = Mesh().mat(M["steel"])
    m.stadium((hx, kz), t0, 6.5, 4, rng(*LINK_Y, ys))
    m.cyl((t0[0], ys * (LINK_Y[1] + ROD_Y) / 2, t0[1]), (0, 1, 0), 1.5, ROD_Y - LINK_Y[1] + 1)
    m.cyl((hx, ys * (BOSS_IN[0] - 0.5 + LINK_Y[1]) / 2, kz), (0, 1, 0), 2.5,
          LINK_Y[1] - BOSS_IN[0] + 0.5)                         # ось колена Ø5
    rig.make(f"{leg}_knee_lever", m, col(C), b_knee, props={"part": f"рычаг голени r {R2:.0f} мм"})

    # тяга M3 с шаровыми наконечниками; длина ROD_L между центрами шаров
    m = Mesh().mat(M["steel"]).cyl((0, ROD_L / 2, 0), (0, 1, 0), 1.5, ROD_L - 8, 16)
    for t in (0, ROD_L):
        m.mat(M["horn"]).sphere((0, t, 0), 3.6)
        m.mat(M["steel"]).cyl((0, t + (4.5 if t == 0 else -4.5), 0), (0, 1, 0), 2.6, 5, 20)
    o = rig.make(f"{leg}_knee_rod", m, col(C), horn, origin=(0, 0, 0),
                 props={"part": "тяга M3 + 2 шаровых наконечника", "rod_length_mm": ROD_L})
    rig.attach(o, horn, (h0[0], ys * ROD_Y, h0[1]))
    c = o.constraints.new('STRETCH_TO')
    c.target, c.subtarget = rig.ARM, f"MCH_{leg}_rod_tip"
    c.rest_length, c.volume = ROD_L * 0.001, 'NO_VOLUME'

    fc = rig.ARM.driver_add(f'pose.bones["{horn}"].rotation_euler', 1)
    drv = fc.driver
    drv.type = 'SCRIPTED'
    v = drv.variables.new()
    v.name, v.type = "k", 'TRANSFORMS'
    t = v.targets[0]
    t.id, t.bone_target = rig.ARM, b_knee
    t.transform_type, t.transform_space = 'ROT_Y', 'LOCAL_SPACE'
    drv.expression = horn_expr()
    return drv.is_simple_expression


def _stop_pts(hx, kz, s0=11.0, s1=22.0, depth=10.0):
    """Упор колена на бедре: грань параллельна переднему краю голени при κ = KNEE_STOP.

    Голень при сгибании κ направлена под ψ = 180° − κ от «вверх» в сторону +X; её край
    (полуширина 8 → 5.5 мм к стопе) смещён к бедру по нормали n. Контакт — по линии s0…s1.
    """
    psi = math.radians(180.0 - KNEE_STOP)
    u = (math.sin(psi), math.cos(psi))
    n = (-math.cos(psi), math.sin(psi))            # к меньшим ψ — в сторону бедра

    def edge(s):
        w = 8.0 - 2.5 * s / (LL - FOOT_R)
        return (hx + s * u[0] + w * n[0], kz + s * u[1] + w * n[1])
    a, b = edge(s0), edge(s1)
    return [a, b, (b[0] + depth * n[0], b[1] + depth * n[1]), (a[0] + depth * n[0], a[1] + depth * n[1])]


def build_leg(leg):
    xs, ys, n0 = LEGS[leg]
    b_abd, b_hip, b_knee = N[n0], N[n0 + 1], N[n0 + 2]
    b_body = rig.ARM.data.bones[b_abd].parent.name
    hx, hz = xs * HX, AXIS_Z

    place_servo(n0, frame((xs * SH_X, ys * SH_Y, hz), (xs, 0, 0), (0, 0, -1)))
    _bracket(leg, xs, ys, hx, hz, b_abd, b_body)
    place_servo(n0 + 1, frame((hx, ys * SHAFT_Y, hz), (0, ys, 0), (0, 0, -1)))

    # бедро: две щёки, бобышка F625 у оси бедра, стяжка над коленом
    m = Mesh().mat(M["accent"])
    m.stadium((hx, hz), (hx, hz - UL), 14, 10, rng(*PLATE_OUT, ys))
    # внутренняя щека: у оси бедра — кольцо (отверстие под ось Ø5 крышки сервы)
    m.ring((hx, ys * sum(PLATE_IN) / 2, hz), (0, 1, 0), 14, 8.1, PLATE_IN[1] - PLATE_IN[0])
    m.stadium((hx, hz - 22), (hx, hz - UL), 14, 10, rng(*PLATE_IN, ys))
    m.ring((hx, ys * sum(BOSS_IN) / 2, hz), (0, 1, 0), 10.5, 8.1, BOSS_IN[1] - BOSS_IN[0])
    m.box((hx - 7, hx + 7), rng(PLATE_IN[1], PLATE_OUT[0], ys), (hz - 92, hz - 82))
    m.prism(_stop_pts(hx, hz - UL), rng(LEG_Y - 6.5, LEG_Y + 6.5, ys))     # упор колена
    rig.make(f"{leg}_thigh", m, col(C), b_hip, bevel=1.0,
             props={"print_orientation": "щекой на стол", "loaded": True,
                    "knee_stop_deg": KNEE_STOP})
    bearing(f"{leg}_bearing_hip_625", "625ZZ", (hx, ys * sum(BOSS_IN) / 2, hz), (0, 1, 0),
            b_hip, b_abd)
    place_servo(n0 + 2, frame((hx + KNEE_U, ys * SHAFT_Y, hz - KNEE_SERVO_D), (0, ys, 0), (0, 0, 1)))

    kz = hz - UL
    for side, y in (("in", PLATE_IN), ("out", PLATE_OUT)):
        bearing(f"{leg}_bearing_knee_{side}_625", "625ZZ", (hx, ys * sum(y) / 2, kz),
                (0, 1, 0), b_hip, b_knee)

    # голень, чаша торсионной пружины (пружину не ставим), стопа TPU
    m = Mesh().mat(M["dark"])
    m.stadium((hx, kz), (hx, kz - LL + FOOT_R), 8, 5.5, rng(LEG_Y - 7, LEG_Y + 7, ys))
    m.ring((hx, ys * 75.0, kz), (0, 1, 0), 11.0, 9.3, 15.0)               # чаша пружины Ø18.6 внутри
    m.box((hx - 1.5, hx + 1.5), rng(68.0, 78.0, ys), (kz - 13.5, kz - 10.5))
    rig.make(f"{leg}_shin", m, col(C), b_knee, bevel=1.0,
             props={"print_orientation": "боком на стол", "loaded": True,
                    "torsion_spring_seat": "чаша Ø22 / Ø18.6 × 15 на оси колена, паз под ножку пружины"})
    sp = P["knee_spring"]
    m = Mesh().mat(M["steel"]).ring((hx, ys * 75.0, kz), (0, 1, 0), sp["od_mm"] / 2,
                                    sp["od_mm"] / 2 - sp["wire_d_mm"], (sp["turns"] + 1) * sp["wire_d_mm"])
    m.box((hx - 1, hx + 1), rng(75.0 - 1, 75.0 + 1, ys), (kz + 7, kz + 16))             # ножка к упору бедра
    rig.make(f"{leg}_knee_spring", m, col("Hardware/Springs"), b_knee,
             props={"part": f"торсион Ø{sp['wire_d_mm']} × {sp['turns']} вит., OD {sp['od_mm']}, "
                            f"натяг {sp['preload_deg_at_65']}° при κ 65°",
                    "mass_g": 8, "group": "Пружины колена", "mounted_on": [f"{leg}_shin", f"{leg}_thigh"],
                    "winding": "левая" if ys > 0 else "правая"})
    m = Mesh().mat(M["tpu"])
    m.sphere((hx, ys * LEG_Y, kz - LL), FOOT_R, (1, 1.1, 0.9))
    rig.make(f"{leg}_foot", m, col(C), b_knee, props={"print_orientation": "TPU 95A, без поддержек"})

    return _knee_linkage(leg, xs, ys, hx, hz, b_hip, b_knee)
