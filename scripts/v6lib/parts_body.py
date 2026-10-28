"""Корпус (две секции), позвоночник 14 pitch / 13 yaw, хвост 15, электроника и питание тела."""
from . import rig
from .geom import Mesh, col, frame, rng
from .layout import (AXIS_Z, BOT, END, GAP2, HW, IN_BOT, IN_TOP, IN_W, N, P, SH_Y, SKIN, SP_P,
                     SP_Y, TAIL, TOP, WALL, WIN_Y)
from .parts import M, place_servo
from . import boards
from .parts_leg import bearing

FRONT, REAR, YOKE = N[13], "Root", N[14]
E = P["electronics"]


SONAR_Z = 200.0                            # центр платы HC-SR04 на груди
SONAR_HOLES = [(133.5, ys * 13, SONAR_Z + 1) for ys in (1, -1)]


def _end_wall(m, s):
    """Торцевая стенка с окнами 24×24: сквозь них ступица качалки отведения (зазор)."""
    x = rng(END - WALL, END, s)
    h0, h1 = AXIS_Z - 12, AXIS_Z + 12
    m.box(x, (-IN_W, IN_W), (IN_BOT, h0))
    m.box(x, (-IN_W, IN_W), (h1, IN_TOP))
    m.box(x, (-(SH_Y - 12), SH_Y - 12), (h0, h1))
    return m


def _section(name, s, bone):
    """s=+1 передняя (x 15…135), −1 задняя. Торец у позвоночника — с окном."""
    xr = rng(GAP2, END, s)
    parts = {
        "lid": lambda m: m.box(xr, (-IN_W - SKIN, IN_W + SKIN), (IN_TOP, TOP)),
        "wall_L": lambda m: m.box(xr, (IN_W, IN_W + SKIN), (IN_BOT, IN_TOP)),
        "wall_R": lambda m: m.box(xr, (-IN_W - SKIN, -IN_W), (IN_BOT, IN_TOP)),
        "end": lambda m: _end_wall(m, s),
    }
    for k, f in parts.items():
        cut = None
        if k == "end" and s > 0:          # отверстия Ø17 под излучатели HC-SR04 (Ø16 + 2 × 0.5)
            cut = Mesh()
            for c in SONAR_HOLES:
                cut.cyl(c, (1, 0, 0), 8.5, 8, 48)
        rig.make(f"Body_{name}_{k}", f(Mesh().mat(M["shell"])), col("Shell"), bone, bevel=1.2,
                 props={"print_orientation": "наружной гранью на стол"}, cut=cut)
    m = Mesh().mat(M["shell"])
    xw = rng(GAP2, GAP2 + WALL, s)
    for ys in (1, -1):
        m.box(xw, rng(WIN_Y, IN_W, ys), (IN_BOT, IN_TOP))
    m.box(xw, (-WIN_Y, WIN_Y), (IN_TOP - 3, IN_TOP))
    m.box(xw, (-WIN_Y, WIN_Y), (IN_BOT, IN_BOT + 2))
    rig.make(f"Body_{name}_spine_frame", m, col("Shell"), bone, bevel=1.0)
    m = Mesh().mat(M["shell"])
    if s > 0:
        m.box(xr, (-IN_W - SKIN, IN_W + SKIN), (IN_BOT - SKIN, IN_BOT))
    else:                                   # люк аккумулятора в дне задней секции
        m.box((-END, -118), (-HW, HW), (BOT, IN_BOT))
        m.box((-42, -GAP2), (-HW, HW), (BOT, IN_BOT))
        for ys in (1, -1):
            m.box((-118, -42), rng(36, HW, ys), (BOT, IN_BOT))
        c = Mesh().mat(M["dark"]).box((-117.7, -42.3), (-35.7, 35.7), (BOT, IN_BOT))
        rig.make("Body_rear_battery_cover", c, col("Shell"), bone, bevel=0.8,
                 props={"print_orientation": "плоско"})
    rig.make(f"Body_{name}_floor", m, col("Shell"), bone, bevel=1.2)


def build_body():
    _section("front", 1, FRONT)
    _section("rear", -1, REAR)
    # yaw: бобышка на дне передней секции, ось — болт M5 в пару 625ZZ вилки; мост под выход сервы 13
    m = Mesh().mat(M["accent"])
    m.cyl((SP_Y.x, 0, IN_BOT + 1), (0, 0, 1), 12, 2)
    m.mat(M["steel"]).cyl((SP_Y.x, 0, IN_BOT + 6), (0, 0, 1), 2.5, 12)
    m.mat(M["accent"])
    m.box((SP_Y.x - 10, SP_Y.x + 10), (-IN_W, IN_W), (211, 214))
    rig.make("Spine_front_mounts", m, col("Structure/Spine"), FRONT, bevel=0.8,
             props={"print_orientation": "мостом на стол", "loaded": True})
    # pitch: стойка на дне задней секции, ось — болт M5 в пару 625ZZ правой щеки вилки
    m = Mesh().mat(M["accent"])
    m.box((SP_P.x - 10, SP_P.x + 10), (-46, -42), (IN_BOT, SP_P.z + 8))
    m.mat(M["steel"]).cyl((SP_P.x, -37, SP_P.z), (0, 1, 0), 2.5, 11)
    rig.make("Spine_rear_post", m, col("Structure/Spine"), REAR, bevel=0.8,
             props={"print_orientation": "боком на стол", "loaded": True})


def build_spine():
    # 14: pitch, DS3235MG в задней секции, вал +Y
    place_servo(14, frame((SP_P.x, 29, SP_P.z), (0, 1, 0), (0, 0, 1)))
    m = Mesh().mat(M["accent"])
    m.cyl((SP_P.x, 32, SP_P.z), (0, 1, 0), 11, 2)
    x1 = SP_Y.x + 13
    m.stadium((SP_P.x, SP_P.z), (SP_Y.x + 11, 185), 12, 10, (33, 36))
    # правая щека начинается от гнезда пары 625ZZ: сквозь него проходит ось стойки
    m.stadium((SP_P.x + 18, SP_P.z - 1), (SP_Y.x + 11, 185), 10, 10, (-36, -33))
    for ys in (1, -1):
        m.box((SP_Y.x - 13, x1), rng(33, 36, ys), (158, 185))
    m.ring((SP_P.x, -33.5, SP_P.z), (0, 1, 0), 11, 8.1, 10)      # гнездо 2 × 625ZZ pitch (Ø16.2)
    for ys in (1, -1):                                            # дно с окном под 625ZZ yaw
        m.box((SP_Y.x - 13, x1), rng(12, 36, ys), (158, 161))
    for xb in ((SP_Y.x - 13, SP_Y.x - 12), (SP_Y.x + 12, x1)):
        m.box(xb, (-12, 12), (158, 161))
    m.ring((SP_Y.x, 0, 160.2), (0, 0, 1), 11, 8.1, 10)            # гнездо 2 × 625ZZ yaw
    for xb in ((SP_Y.x - 37.25, SP_Y.x - 30.6), (SP_Y.x + 10.6, SP_Y.x + 17.25)):
        m.box(xb, (-33, 33), (191, 194))
    rig.make("Spine_yoke", m, col("Structure/Spine"), YOKE, bevel=1.0,
             props={"print_orientation": "щекой на стол", "loaded": True})
    for i, y in enumerate((-36, -31)):
        bearing(f"Spine_bearing_pitch_{i + 1}_625", "625ZZ", (SP_P.x, y, SP_P.z), (0, 1, 0), YOKE, REAR)
    for i, z in enumerate((157.7, 162.7)):
        bearing(f"Spine_bearing_yaw_{i + 1}_625", "625ZZ", (SP_Y.x, 0, z), (0, 0, 1), YOKE, FRONT)
    # 13: yaw, MG996R в вилке, вал +Z, выход — на мост передней секции
    place_servo(13, frame((SP_Y.x, 0, 205), (0, 0, 1), (1, 0, 0)))


def build_power_panel():
    """Рамка на заднем торце: XT60 (заряд/питание) и гнездо loop-key — снаружи, без разборки."""
    m = Mesh().mat(M["dark"])
    for z in ((156, 159), (177, 180)):
        m.box((-END - 6, -END), (-26, 26), z)       # кронштейн плеча при отведении — с y ≈ 28
    for y in ((-26, -24), (-6, 6), (24, 26)):
        m.box((-END - 6, -END), y, (159, 177))
    rig.make("Rear_power_panel", m, col("Shell"), REAR, bevel=0.6,
             props={"print_orientation": "лицом на стол",
                    "access": "XT60 loop-key вставляется снаружи; ключ вынут = питание разорвано"})


def build_bridges():
    """Мосты груди и кормы: 625ZZ на осях отведения перед качалкой (болт M5 из кронштейна).

    Грудь: перемычка снизу (над ней — поле HC-SR04); корма: перемычка сверху (под ней —
    рамка XT60, ключ вставляется снизу перемычки).
    """
    for s, name, bone, zb in ((1, "Chest_bridge", FRONT, (156, 164)), (-1, "Stern_bridge", REAR, (186, 194))):
        m = Mesh().mat(M["accent"])
        xb = rng(END + 8, END + 12, s)
        m.box(xb, (-56, 56), zb)
        for ys in (1, -1):
            m.ring((s * (END + 10.5), ys * SH_Y, AXIS_Z), (1, 0, 0), 11, 8.1, 5)
        posts = [(-8, 8)] if s > 0 else [(14, 22), (-22, -14)]
        for yb in posts:
            m.box(rng(END, END + 8, s), yb, zb)
        rig.make(name, m, col("Structure/Body"), bone, bevel=1.0,
                 props={"print_orientation": "лицом на стол", "loaded": True,
                        "mounted_on": [f"Body_{'front' if s > 0 else 'rear'}_end"]})


def build_tray():
    """Полка электроники задней секции над аккумулятором (на термовставках в стенки)."""
    m = Mesh().mat(M["dark"])
    m.box((-END + WALL, -89), (-34, 34), TRAY_Z)          # между сервами отведения
    m.box((-89, -43), (-IN_W, IN_W), TRAY_Z)
    m.mat(M["steel"])
    for dx in (10.2, -10.2):
        for y in (28.75, -28.75):
            m.cyl((PCA_C[0] + dx, y, TRAY_Z[1] + 2), (0, 0, 1), 2.25, 4, 16)   # стойки M2.5 × 4
    rig.make("Body_rear_tray", m, col("Structure/Body"), REAR, bevel=0.6,
             props={"print_orientation": "плоско",
                    "mounted_on": ["Body_rear_end", "Body_rear_wall_L", "Body_rear_wall_R",
                                   "PCA9685_Body"]})
    # контакты док-станции: две площадки снизу дна + подпружиненные гильзы (резерв, не закуплено)
    m = Mesh().mat(M["gold"])
    for xb in ((-40, -31), (-28, -19)):                    # справа от сервы 14 (она до дна)
        m.box(xb, (-23, -13), (BOT - 0.6, BOT))
        m.mat(M["steel"]).cyl((sum(xb) / 2, -18, IN_BOT + 1.2), (0, 0, 1), 3, 2.4, 16).mat(M["gold"])
    rig.make("Dock_contacts_reserved", m, col("Electronics/Power"), REAR,
             props={"part": E["Dock_contacts"]["board"], "mass_g": 0, "purchased": False,
                    "group": "Не в смете", "mounted_on": ["Body_rear_floor"]})


def build_tail():
    m = Mesh().mat(M["shell"])
    m.box((-172, -END), (-24, 8.5), (196, 222))
    rig.make("Tail_housing", m, col("Structure/Tail"), REAR, bevel=2.0)
    place_servo(15, frame((TAIL.x, 6, TAIL.z), (0, 1, 0), (1, 0, 0)))
    m = Mesh().mat(M["accent"])
    m.cyl((TAIL.x, 10.1, TAIL.z), (0, 1, 0), 7, 1.8)
    m.stadium((TAIL.x, TAIL.z), (-180, 214), 8, 6, (11, 14))
    m.box((-186, -176), (-6, 14), (208, 220))
    m.mat(M["dark"])
    m.cyl((-196, 0, 226), (-0.6, 0, 0.8), 6.5, 32, 24, r2=3.0)
    m.sphere((-206, 0, 239), 3.2)
    rig.make("Tail", m, col("Structure/Tail"), N[15], bevel=0.6,
             props={"print_orientation": "щекой на стол"})


TRAY_Z = (178.0, 180.0)
PCA_C = (-84.9, 0.0)
BOX = {  # питание — по power.md, «не закуплено»: (коллекция, x, y, z, материал, кость, ключ params.electronics)
    "UBEC_F_6V_20A": ("Power", (70, 97), (-23, 23), (154, 167), "pcb_k", FRONT, "UBEC_F"),
    "Cap_UBEC_F_2200uF": ("Power", (62, 87), (24, 36.5), (154, 166.5), "pcb_k", FRONT, "Capacitors"),
    "DCDC_5V_5A": ("Power", (100, 121), (-8, 8), (154, 159), "pcb_b", FRONT, "DCDC_5V_5A"),
    "MOSFET_F": ("Power", (100, 120), (-12.5, 12.5), (162, 167), "pcb_b", FRONT, "MOSFET_switches"),
    "Fuse_F_25A": ("Power", (100, 118), (13, 21), (154, 169), "accent", FRONT, "Fuses"),
    "Fuse_logic_5A": ("Power", (100, 118), (-21, -13), (154, 169), "accent", FRONT, "Fuses"),
    "Battery_2S2P_P28A": ("Power", (-118, -42), (-33.5, 33.5), (153.2, 173), "bat", REAR, "Battery_2S2P"),
    "BMS_2S_40A": ("Power", (-100, -55), (-10, 10), (173, 177), "pcb_b", REAR, "BMS"),
    "UBEC_R_6V_20A": ("Power", (-126, -99), (-23, 23), (180, 193), "pcb_k", REAR, "UBEC_R"),
    "MOSFET_R": ("Power", (-125, -100), (-22, -2), (196, 201), "pcb_b", REAR, "MOSFET_switches"),
    "Fuse_R_25A": ("Power", (-126, -101), (25, 33), (180, 195), "accent", REAR, "Fuses"),
    "Fuse_main_40A": ("Power", (-41, -20), (-34, -24), (157, 172), "accent", REAR, "Fuses"),
    "XT60_port": ("Power", (-139, -END), (-23, -7), (160, 176), "accent", REAR, "XT60_loopkey"),
    "XT60_loopkey_switch": ("Power", (-139, -END), (7, 23), (160, 176), "accent", REAR, "XT60_loopkey"),
}
MOUNTS = {"BMS_2S_40A": ["Battery_2S2P_P28A"], "XT60_port": ["Body_rear_end", "Rear_power_panel"],
          "XT60_loopkey_switch": ["Body_rear_end", "Rear_power_panel"],
          "UBEC_R_6V_20A": ["Body_rear_tray"], "Fuse_R_25A": ["Body_rear_tray"],
          "Cap_head_2200uF": ["Head_shell"]}


def build_electronics(table=BOX):
    """Питание — габаритными блоками (не закуплено, место зарезервировано)."""
    for name, (c, x, y, z, mk, bone, key) in table.items():
        m = Mesh().mat(M[mk]).box(x, y, z)
        rig.make(name, m, col(f"Electronics/{c}"), bone,
                 origin=((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, z[0]),
                 props={"part": E[key]["board"], "mass_g": E[key]["mass_g"], "purchased": False,
                        "group": "Питание (не закуплено)", "mounted_on": MOUNTS.get(name, [])})


def build_boards():
    """Платы и датчики тела по смете (v6lib.boards)."""
    P_ = boards.place
    # передняя секция: HC-SR04 на груди, «Связь» C3 под крышкой у левого борта, передний IMU
    P_("Sonar_HCSR04", "hcsr04", (121.9, 0, SONAR_Z), (1, 0, 0), (0, 1, 0), "Body", FRONT, "Sonar_HCSR04",
       {"mounted_on": ["Body_front_end"], "access": "излучатели в отверстиях Ø17 груди"})
    P_("ESP32_Comms", "c3mini", (49, 39.25, IN_TOP - 1), (0, 0, -1), (0, 1, 0), "Comms", FRONT, "ESP32_Comms",
       {"mounted_on": ["Body_front_lid"], "antenna": "к левому борту и крышке (PETG), силовые провода — справа"})
    P_("CAN_transceiver_Comms", "sn65", (52, 17.5, IN_TOP - 1), (0, 0, -1), (1, 0, 0), "Comms", FRONT,
       "CAN_transceiver", {"mounted_on": ["Body_front_lid"], "terminator": "снять"})
    P_("IMU_front_MPU6050_0x69", "gy521", (57.5, 0, IN_BOT + 0.5), (0, 0, 1), (1, 0, 0), "Body", FRONT,
       "IMU_front", {"mounted_on": ["Body_front_floor"]})
    # задняя секция: полка — PCA9685, «Тело», CAN; задний IMU на дне
    P_("ESP32_Body", "devkit_ch340", (-57, 0, TRAY_Z[1] + 10.5), (0, 0, 1), (0, 1, 0), "Body", REAR,
       "ESP32_Body", {"mounted_on": ["Body_rear_tray"]})
    P_("PCA9685_Body", "pca9685", (PCA_C[0], 0, TRAY_Z[1] + 4), (0, 0, 1), (0, 1, 0), "Body", REAR,
       "PCA9685_Body", {"mounted_on": ["Body_rear_tray"]})
    P_("CAN_transceiver_Body", "sn65", (-56, 43.5, TRAY_Z[1] + 0.2), (0, 0, 1), (1, 0, 0), "Body", REAR,
       "CAN_transceiver", {"mounted_on": ["Body_rear_tray"], "terminator": "оставить 120 Ом"})
    P_("IMU_rear_MPU6050_0x68", "gy521", (-58, -47, IN_BOT + 0.5), (0, 0, 1), (1, 0, 0), "Body", REAR,
       "IMU_rear", {"mounted_on": ["Body_rear_floor"]})
    m = Mesh().mat(M["pcb_k"]).cyl((-79, -16, TRAY_Z[1] + 5.6 + 10), (0, 0, 1), 6.25, 20, 32)
    rig.make("Cap_PCA9685_2200uF", m, col("Electronics/Power"), REAR,
             props={"part": E["Capacitors"]["board"], "mass_g": E["Capacitors"]["mass_g"],
                    "purchased": False, "group": "Питание (не закуплено)", "mounted_on": ["PCA9685_Body"]})
