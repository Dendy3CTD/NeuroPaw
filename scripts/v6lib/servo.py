"""Модели сервоприводов MG996R / MG90S / SG90.

Локальная система сервы: начало — основание шлицевого вала (на нём сидит качалка),
вал по +Z, корпус уходит в −Z, длинная сторона корпуса — по X, вал смещён к +X.
"""
import math

from mathutils import Matrix, Vector

from .geom import mat

# Размеры по даташитам: L×W×H (H — полная высота с валом), ушки, шлицы
SPEC = {
    "MG996R": dict(L=40.7, W=19.7, H=42.9, shaft_h=4.0, dome_h=2.0, off=10.0,
                   tab_len=54.5, tab_z=(-11.0, -8.5), spline_r=2.9, teeth=25,
                   color=(0.015, 0.015, 0.015)),
    "DS3235MG": dict(L=40.0, W=20.0, H=40.5, shaft_h=4.0, dome_h=2.0, off=10.0,
                     tab_len=54.5, tab_z=(-10.5, -8.0), spline_r=2.9, teeth=25,
                     color=(0.16, 0.17, 0.19)),
    "MG90S": dict(L=22.8, W=12.2, H=28.5, shaft_h=3.2, dome_h=4.0, off=5.9,
                  tab_len=32.5, tab_z=(-8.4, -6.0), spline_r=2.4, teeth=20,
                  color=(0.03, 0.12, 0.6)),
    "SG90": dict(L=22.2, W=11.8, H=31.0, shaft_h=3.2, dome_h=4.5, off=5.9,
                 tab_len=32.2, tab_z=(-9.0, -6.6), spline_r=2.4, teeth=21,
                 color=(0.25, 0.62, 0.95)),
}


def depth(kind):
    """Насколько корпус уходит ниже начала координат (мм)."""
    s = SPEC[kind]
    return s["H"] - s["shaft_h"]


def build(mesh, kind, m):
    """Добавляет серву типа kind в mesh, матрица m — из geom.frame()."""
    s = SPEC[kind]
    L, W, off = s["L"], s["W"], s["off"]
    case_h = s["H"] - s["shaft_h"] - s["dome_h"]
    x0, x1 = -off - L / 2, -off + L / 2
    top = -s["dome_h"]

    m_case = mat(f"Servo_{kind}", s["color"], 0.5)
    m_label = mat("Servo_label", (0.82, 0.83, 0.85), 0.35)
    m_spline = mat("Spline_brass", (0.8, 0.6, 0.25), 0.3, 1.0)
    wires = [mat("Wire_brown", (0.18, 0.08, 0.03), 0.6),
             mat("Wire_red", (0.7, 0.03, 0.02), 0.6),
             mat("Wire_orange", (0.95, 0.4, 0.02), 0.6)]

    mesh.mat(m_case)
    mesh.box((x0, x1), (-W / 2, W / 2), (top - case_h, top), m)
    # крепёжные ушки со щелью под винт, как у оригинала
    ear = (s["tab_len"] - L) / 2
    slot = 1.0 if kind == "MG996R" else 0.8
    for sgn, xe in ((1, x1), (-1, x0)):
        base = rng_x(xe, xe + sgn * ear * 0.35)
        mesh.box(base, (-W / 2, W / 2), s["tab_z"], m)
        prong = rng_x(xe + sgn * ear * 0.35, xe + sgn * ear)
        for ys in (1, -1):
            mesh.box(prong, sorted((ys * slot, ys * W / 2)), s["tab_z"], m)
    # купол редуктора и вторая шестерня
    mesh.cyl((0, 0, top / 2), (0, 0, 1), W / 2, s["dome_h"], 40, m)
    mesh.cyl((-W * 0.55, 0, top / 2 - 0.3), (0, 0, 1), W * 0.28, s["dome_h"] - 0.6, 24, m)
    # шлицевой вал
    mesh.mat(m_spline)
    r, h = s["spline_r"], s["shaft_h"]
    mesh.cyl((0, 0, h / 2), (0, 0, 1), r - 0.25, h, 32, m)
    tw = 2 * math.pi * r / s["teeth"] * 0.5
    for i in range(s["teeth"]):
        a = 2 * math.pi * i / s["teeth"]
        tm = m @ Matrix.Rotation(a, 4, 'Z') @ Matrix.Translation((r - 0.2, 0, 0))
        mesh.box((-0.25, 0.25), (-tw / 2, tw / 2), (0.2, h), tm)
    # наклейка на боковой грани
    mesh.mat(m_label)
    mesh.box((x0 + L * 0.1, x1 - L * 0.1), (W / 2, W / 2 + 0.15),
             (top - case_h * 0.72, top - case_h * 0.22), m)
    # выход провода у дальнего торца, внизу корпуса
    mesh.mat(m_case)
    zc = top - case_h + 3.0
    mesh.box((x0 - 2.5, x0), (-3.2, 3.2), (zc - 2, zc + 2), m)
    # провод: 4 мм от торца, затем изгиб вдоль низа корпуса (не в стенку)
    for i, wm in enumerate(wires):
        mesh.mat(wm)
        yi = (i - 1) * 1.25
        mesh.cyl((x0 - 4.5, yi, zc), (1, 0, 0), 0.6, 4, 10, m)
        mesh.cyl((x0 - 6.5, yi, zc - 3), (0, 0, 1), 0.6, 6, 10, m)
    return mesh


def rng_x(a, b):
    return tuple(sorted((a, b)))


def shaft_tip(m, kind):
    """Мировая точка торца вала."""
    return m @ Vector((0, 0, SPEC[kind]["shaft_h"]))
