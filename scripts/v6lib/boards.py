"""Покупные модули по смете: плата реальных габаритов, крепёжные отверстия, разъёмы.

Локальная система модуля: начало — центр нижней грани платы, X — длина, Y — ширина,
Z — нормаль со стороны компонентов. Размеры — по даташитам и типовым платам;
где точных данных нет, параметр params.electronics[...]["measure"] = True
(см. docs/assumptions.md).
"""
from . import rig
from .geom import Mesh, col, frame
from .layout import P
from .parts import M

T = 1.6                     # толщина платы
E = P["electronics"]


def _pcb(g, m, L, W, mk="pcb_k"):
    g.mat(M[mk]).box((-L / 2, L / 2), (-W / 2, W / 2), (0, T), m)


def _usbc(g, m, x_end, y):
    """USB-C на торце −X: 8.94 × 7.35 × 3.26, выступ 0.6 мм."""
    g.mat(M["steel"]).box((x_end - 0.6, x_end + 6.75), (y - 4.47, y + 4.47), (T, T + 3.26), m)


def _header(g, m, n, y, down=True, x_c=0.0, along="x", pitch=2.54):
    """Гребёнка 2.54: пластик 2.5 мм у платы, штыри 8.5 мм вниз (или вверх)."""
    z = (-2.5, 0) if down else (T, T + 2.5)
    zp = (-8.5, T + 0.8) if down else (0, T + 8.5)
    half = n * pitch / 2
    if along == "x":
        g.mat(M["dark"]).box((x_c - half, x_c + half), (y - 1.25, y + 1.25), z, m)
    else:
        g.mat(M["dark"]).box((y - 1.25, y + 1.25), (x_c - half, x_c + half), z, m)
    g.mat(M["gold"])
    for i in range(n):
        p = x_c - (n - 1) * pitch / 2 + i * pitch
        xy = ((p - 0.32, p + 0.32), (y - 0.32, y + 0.32))
        g.box(*(xy if along == "x" else xy[::-1]), zp, m)


def _pads(g, m, n, y, x_c=0.0, along="x", pitch=2.54):
    """Площадки под пайку проводов (гребёнку не ставим)."""
    g.mat(M["gold"])
    for i in range(n):
        p = x_c - (n - 1) * pitch / 2 + i * pitch
        xy = ((p - 0.8, p + 0.8), (y - 0.8, y + 0.8))
        g.box(*(xy if along == "x" else xy[::-1]), (T, T + 0.05), m)


def _holes(c, m, pts, d):
    for x, y in pts:
        c.cyl((x, y, T / 2), (0, 0, 1), d / 2, T + 2, 20, m=m)


def devkit_ch340(g, c, m):
    """ESP32 DevKit CH340, 38 выводов: 55 × 28, гребёнки вниз, отверстий нет (ложемент)."""
    _pcb(g, m, 55, 28)
    g.mat(M["pcb_k"]).box((1.5, 27.5), (-9, 9), (T, T + 0.8), m)          # модуль WROOM-32
    g.mat(M["steel"]).box((1.5, 19.5), (-8, 8), (T + 0.8, T + 3.1), m)   # экран модуля
    g.mat(M["steel"]).box((-28.1, -22.4), (-3.75, 3.75), (T, T + 2.5), m)  # micro-USB
    g.mat(M["dark"]).box((-17, -12), (3, 7), (T, T + 1.5), m)            # CH340C
    g.box((-10, -4), (-8.5, -5), (T, T + 1.6), m)                        # AMS1117
    for y in (-10, 10):
        g.box((-24, -20), (y - 1.75, y + 1.75), (T, T + 1.5), m)         # EN / BOOT
    for y in (-12.7, 12.7):
        _header(g, m, 19, y)


def devkitc1(g, c, m):
    """ESP32-S3-DevKitC-1 N16R8: 69 × 26, 2 × USB-C (USB, UART), гребёнки 2 × 22 вниз."""
    _pcb(g, m, 69, 26)
    g.mat(M["pcb_k"]).box((9, 34.5), (-9, 9), (T, T + 0.8), m)           # WROOM-1
    g.mat(M["steel"]).box((9, 27), (-8.5, 8.5), (T + 0.8, T + 3.2), m)
    for y in (-6.5, 6.5):
        _usbc(g, m, -34.5, y)
    g.mat(M["dark"])
    for y in (-8, 8):
        g.box((-24, -20.5), (y - 1.75, y + 1.75), (T, T + 1.5), m)       # BOOT / RST
    g.mat(M["eye"]).box((-18, -16.4), (-0.8, 0.8), (T, T + 0.6), m)      # RGB-светодиод
    for y in (-11.43, 11.43):
        _header(g, m, 22, y)


def s3cam(g, c, m):
    """ESP32-S3-CAM N16R8: 64 × 27 (замерить), USB-C «USB» (+Y, нативный) и «COM» (−Y)."""
    _pcb(g, m, 64, 27)
    g.mat(M["pcb_k"]).box((6.5, 32), (-9, 9), (T, T + 0.8), m)
    g.mat(M["steel"]).box((6.5, 24.5), (-8.5, 8.5), (T + 0.8, T + 3.2), m)
    g.mat(M["dark"]).box((0, 5), (-8, 8), (T, T + 1.2), m)               # FPC 24 pin камеры
    for y in (-6.5, 6.5):
        _usbc(g, m, -32, y)
    g.mat(M["dark"]).box((-20, -15), (-2.5, 2.5), (T, T + 1.2), m)       # CH343
    for y in (-12, 12):
        _pads(g, m, 20, y)


def c3mini(g, c, m):
    """ESP32-C3 SuperMini: 22.5 × 18, USB-C на −X, керамическая антенна на +X."""
    _pcb(g, m, 22.5, 18, "pcb_b")
    _usbc(g, m, -11.25, 0)
    g.mat(M["dark"]).box((-1, 4), (-2.5, 2.5), (T, T + 0.9), m)
    g.mat(M["shell"]).box((7, 10.5), (-3, 3), (T, T + 1.2), m)           # антенна
    for y in (-7.8, 7.8):
        _pads(g, m, 8, y)


def sn65(g, c, m):
    """SN65HVD230: 20 × 15 (замерить), 3V3/GND/CTX/CRX и CANH/CANL — пайкой."""
    _pcb(g, m, 20, 15, "pcb_b")
    g.mat(M["dark"]).box((-2.5, 2.5), (-3.1, 3.1), (T, T + 1.75), m)
    g.box((4, 6), (2, 3.3), (T, T + 0.5), m)                             # 120 Ом
    _pads(g, m, 4, -8.7, along="y")
    _pads(g, m, 2, 8.7, along="y")
    _holes(c, m, [(5.5, 5.5), (5.5, -5.5)], 2.2)


def pca9685(g, c, m):
    """PCA9685: 62.5 × 25.4, 4 × Ø2.5, 16 × 3 штыря серв вверх, клеммник V+, 6 штырей по торцам."""
    _pcb(g, m, 62.5, 25.4, "pcb_b")
    _holes(c, m, [(sx * 28.75, sy * 10.2) for sx in (1, -1) for sy in (1, -1)], 2.5)
    g.mat(M["dark"]).box((-20.3, 20.3), (4.85, 12.45), (T, T + 2.5), m)
    g.box((-5, 5), (-4.5, 0), (T, T + 1.2), m)                           # PCA9685 TSSOP
    g.mat(M["gold"])
    for i in range(16):
        x = -19.05 + i * 2.54
        for y in (6.12, 8.66, 11.2):
            g.box((x - 0.32, x + 0.32), (y - 0.32, y + 0.32), (0, T + 8.5), m)
    g.mat(M["pcb_b"]).box((-5.1, 5.1), (-12.7, -5.1), (T, T + 10), m)    # клеммник V+
    for xs in (1, -1):
        _header(g, m, 6, xs * 29.2, down=False, along="y")


def gy521(g, c, m):
    """GY-521 MPU-6050: 21.2 × 16.4, 2 × Ø3, 8 выводов — пайкой (витая пара)."""
    _pcb(g, m, 21.2, 16.4, "pcb_b")
    _holes(c, m, [(7.62, 4.95), (-7.62, 4.95)], 3.0)
    g.mat(M["dark"]).box((-2, 2), (-1.5, 2.5), (T, T + 0.9), m)
    g.box((-9, -6), (-1, 2), (T, T + 1.2), m)
    _pads(g, m, 8, -6.9)


def hcsr04(g, c, m):
    """HC-SR04: 45 × 20, излучатели Ø16 × 12 (центры ±13), 4 × Ø1.8, гребёнка 90° вниз (−Y)."""
    _pcb(g, m, 45, 20, "pcb_b")
    _holes(c, m, [(sx * 20.5, sy * 8) for sx in (1, -1) for sy in (1, -1)], 1.8)
    for x in (-13, 13):
        g.mat(M["steel"]).cyl((x, 1, T + 6), (0, 0, 1), 8, 12, 40, m=m)
        g.mat(M["dark"]).cyl((x, 1, T + 12.05), (0, 0, 1), 6.5, 0.2, 40, m=m)   # сетка
    g.mat(M["steel"]).box((-4.5, 4.5), (4.5, 8.5), (T, T + 3.5), m)      # кварц
    g.mat(M["dark"]).box((-5.08, 5.08), (-10, -7.5), (-2.5, 0), m)
    g.mat(M["gold"])
    for i in range(4):
        x = -3.81 + i * 2.54
        g.box((x - 0.32, x + 0.32), (-16, -7.5), (-1.6, -0.96), m)


def ina226(g, c, m):
    """INA226 (CJMCU-226): 20 × 25, шунт R100 2512, 2 × Ø3."""
    _pcb(g, m, 20, 25, "pcb_b")
    _holes(c, m, [(6.5, 9.5), (6.5, -9.5)], 3.0)
    g.mat(M["dark"]).box((-3.2, 3.2), (6, 9.2), (T, T + 0.6), m)
    g.box((-1.5, 1.5), (-1.5, 1.5), (T, T + 1.0), m)
    _pads(g, m, 8, -8.7, along="y")


def max98357(g, c, m):
    """MAX98357A: 18 × 19, клеммник не впаян — провода динамика пайкой."""
    _pcb(g, m, 18, 19, "pcb_b")
    g.mat(M["dark"]).box((-1.5, 1.5), (-1.5, 1.5), (T, T + 0.9), m)
    _pads(g, m, 7, -7.7, along="y")
    _pads(g, m, 2, 7.7, along="y", pitch=5.0)


def inmp441(g, c, m):
    """INMP441: круглая Ø14, микрофон снизу (к стенке), отверстие звука Ø1 в центре."""
    g.mat(M["pcb_b"]).cyl((0, 0, T / 2), (0, 0, 1), 7, T, 32, m=m)
    g.mat(M["steel"]).box((-2, 2), (-1.5, 1.5), (-1, 0), m)
    _pads(g, m, 6, 4.4, pitch=1.9)
    c.cyl((0, 0, T / 2), (0, 0, 1), 0.5, T + 3, 12, m=m)


def gc9a01(g, c, m):
    """GC9A01 1.28": круглая плата Ø38.6, стекло Ø35.6 × 2.1, хвостовик с 7 площадками и 2 × Ø2."""
    g.mat(M["pcb_b"]).cyl((0, 0, T / 2), (0, 0, 1), 19.3, T, 64, m=m)
    g.box((-6, 6), (-24.5, -17), (0, T), m)
    g.mat(M["glass"]).cyl((0, 0, T + 1.0), (0, 0, 1), 17.8, 2.0, 64, m=m)
    g.mat(M["eye"]).cyl((0, 0, T + 2.05), (0, 0, 1), 16.2, 0.1, 64, m=m)
    g.mat(M["dark"]).box((-4, 4), (-4, 4), (-0.9, 0), m)                 # драйвер на обороте
    _pads(g, m, 7, -22.6, pitch=1.5)
    _holes(c, m, [(-4.5, -19.6), (4.5, -19.6)], 2.0)


def speaker(g, c, m):
    """Динамик 35 × 25 × 5 (замерить), ушки с Ø2, диффузор к +Z."""
    g.mat(M["dark"]).box((-17.5, 17.5), (-12.5, 12.5), (0, 4.5), m)
    g.mat(M["pcb_k"]).box((-14.5, 14.5), (-9.5, 9.5), (4.5, 4.7), m)
    g.mat(M["dark"])
    for xs in (1, -1):
        g.box(sorted((xs * 17.5, xs * 20.5)), (-3, 3), (3.5, 4.5), m)
    g.mat(M["gold"]).box((-3, 3), (-14, -12.5), (0, 1), m)
    c.cyl((19, 0, 4), (0, 0, 1), 1.0, 3, 12, m=m)
    c.cyl((-19, 0, 4), (0, 0, 1), 1.0, 3, 12, m=m)


def usb_flash(g, c, m):
    """Флешка USB-A: корпус 33 × 16 × 7, штекер 12 мм (−X), всего 45 мм."""
    g.mat(M["dark"]).box((0, 33), (-8, 8), (-3.5, 3.5), m)
    g.mat(M["steel"]).box((-12, 0), (-6, 6), (-2.25, 2.25), m)


def otg_socket(g, c, m):
    """Гнездо USB-A на конце гибкого OTG-кабеля: 22 × 15 × 8, вход на −X."""
    g.mat(M["dark"]).box((-12, 10), (-7.5, 7.5), (-4, 4), m)


def otg_plug90(g, c, m):
    """Угловой штекер USB-C: металл 6.65 мм (−X), корпус 12 × 9 × 7, кабель к +Z."""
    g.mat(M["steel"]).box((-6.65, 0), (-4.2, 4.2), (-1.3, 1.3), m)
    g.mat(M["dark"]).box((0, 6.5), (-4.5, 4.5), (-3.5, 3.5), m)
    g.box((0.5, 6), (-3.5, 3.5), (3.5, 6), m)


def ov2640(g, c, m):
    """Камера OV2640 платы S3-CAM: 8.5 × 8.5 × 5 + объектив Ø7, взгляд к +Z."""
    g.mat(M["dark"]).box((-4.25, 4.25), (-4.25, 4.25), (0, 5), m)
    g.mat(M["lens"]).cyl((0, 0, 6.5), (0, 0, 1), 3.5, 3, 32, m=m)
    g.mat(M["gold"]).box((-4.25, 4.25), (-12, -4.25), (0, 0.3), m)


BUILD = {"devkit_ch340": devkit_ch340, "devkitc1": devkitc1, "s3cam": s3cam, "c3mini": c3mini,
         "sn65": sn65, "pca9685": pca9685, "gy521": gy521, "hcsr04": hcsr04, "ina226": ina226,
         "max98357": max98357, "inmp441": inmp441, "gc9a01": gc9a01, "speaker": speaker,
         "usb_flash": usb_flash, "otg_socket": otg_socket, "otg_plug90": otg_plug90, "ov2640": ov2640}


def place(name, kind, origin, z_axis, x_axis, coll, bone, key, props=None, mass_g=None):
    """Модуль kind в точке origin (центр низа платы); z_axis — сторона компонентов."""
    m = frame(origin, z_axis, x_axis)
    g, c = Mesh(), Mesh()
    BUILD[kind](g, c, m)
    e = E[key]
    pr = {"part": e["board"], "mass_g": e["mass_g"] if mass_g is None else mass_g,
          "estimate_row": e["estimate_row"] or 0, "measure": e["measure"],
          "purchased": e["purchased"], "group": "Электроника" if e["purchased"] else "Не в смете"}
    pr.update(props or {})
    return rig.make(name, g, col(f"Electronics/{coll}"), bone, origin=origin,
                    cut=c if c.bm.faces else None, props=pr)
