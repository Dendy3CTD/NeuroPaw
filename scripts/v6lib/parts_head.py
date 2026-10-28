"""Шея 16/17, голова с челюстью 18, уши 19/20; платы «Мозг» и «Органы чувств» в голове."""
from . import boards, rig
from .geom import Mesh, col, frame, rng
from .layout import EAR, JAW, N, NECK_P, NECK_Y, TOP
from .parts import M, place_servo
from .parts_body import FRONT, build_electronics
from .parts_leg import bearing

NECK, HEAD = N[16], N[17]
HX0, HX1, HY, HZ0, HZ1 = 112.0, 182.0, 47.0, 288.0, 352.0   # оболочка головы
HW_ = 2.5                                                   # стенка головы
EYE_Z, EYE_Y = 330.0, 24.5                                  # центры экранов; камера между ними
THR_Z = (NECK_Y.z + 2.2, NECK_Y.z + 11.2)                   # упорный 51100 над куполом MG90S
MIC = (150.0, 43.4, 319.0)                                  # микрофоны под осями ушей
SENSES_O = (129.0, 0.0, 309.5)                              # центр низа платы «Органов чувств»
BRAIN_O = (162.0, 0.0, 335.0)                               # «Мозг» за глазами: штатный шлейф камеры 21 мм
FLASH_Y, FLASH_Z = -10.5, 316.0                             # основание штекера флешки
HATCH_Z = (312.0, 332.0)                                    # лючок: флешка и USB-C «COM» «Мозга»


def build_neck():
    # основание шеи на крышке: плита + стойки под ушки сервы 16; справа — стойка с болтом M5
    m = Mesh().mat(M["accent"])
    m.box((80, 140), (-24, 24), (TOP, TOP + 3))
    for xb in ((81, 89.3), (130.7, 138.5)):
        m.box(xb, (-12, 8.2), (TOP + 3, 244))
    m.box((112, 128), (-40, -36), (TOP, NECK_P.z + 9))
    m.mat(M["steel"]).cyl((NECK_P.x, -29.5, NECK_P.z), (0, 1, 0), 2.5, 13, 20)   # ось M5
    rig.make("Neck_base", m, col("Structure/Neck"), FRONT, bevel=1.0,
             props={"print_orientation": "плитой на стол", "loaded": True})
    place_servo(16, frame((NECK_P.x, 19.5, NECK_P.z), (0, 1, 0), (1, 0, 0)))

    # звено шеи: качалка, две щёки, гнездо 2 × 625ZZ справа, рамка MG90S (17), площадка 51100
    m = Mesh().mat(M["accent"])
    m.cyl((NECK_P.x, 24.5, NECK_P.z), (0, 1, 0), 10, 2)
    m.stadium((NECK_P.x, NECK_P.z), (NECK_P.x - 4, 268), 13, 10, (25.5, 28.5))
    m.ring((NECK_P.x, -28.5, NECK_P.z), (0, 1, 0), 11, 8.1, 10)
    m.stadium((NECK_P.x - 1, NECK_P.z + 18), (NECK_P.x - 4, 268), 10, 10, (-28.5, -25.5))
    z0, z1 = NECK_Y.z - 11.4, NECK_Y.z - 8.4           # под ушками MG90S
    for xb in ((96, 102.4), (125.8, 132)):
        m.box(xb, (-28.5, 28.5), (z0, z1))
    for ys in (1, -1):
        m.box((102.4, 125.8), rng(6.4, 28.5, ys), (z0, z1))
        m.box((106, 122), rng(7.5, 10.5, ys), (z1, THR_Z[0]))                 # стойки площадки
    m.ring((NECK_Y.x, 0, THR_Z[0] - 1), (0, 0, 1), 14, 5.5, 2)                # площадка под 51100
    rig.make("Neck_link", m, col("Structure/Neck"), NECK, bevel=1.0,
             props={"print_orientation": "щекой на стол", "loaded": True})
    for i, y in enumerate((-31, -26)):
        bearing(f"Neck_bearing_pitch_{i + 1}_625", "625ZZ", (NECK_P.x, y, NECK_P.z), (0, 1, 0), NECK, FRONT)
    bearing("Neck_bearing_yaw_51100", "51100", (NECK_Y.x, 0, sum(THR_Z) / 2), (0, 0, 1), NECK, HEAD)
    place_servo(17, frame(tuple(NECK_Y), (0, 0, 1), (1, 0, 0)))


def _head_shell():
    m = Mesh().mat(M["shell"])
    m.box((HX0, HX1), (-HY, HY), (HZ1 - HW_, HZ1))                       # верх
    m.box((HX0, 160), (-HY, HY), (HZ0, HZ0 + HW_))                      # низ (спереди окно челюсти)
    m.box((HX0, HX1), (HY - HW_, HY), (HZ0, HZ1))                       # левый бок
    m.box((HX0, 158), (-HY, -HY + HW_), (HZ0, HZ1))                     # правый бок с лючком
    m.box((158, HX1), (-HY, -HY + HW_), (HZ0, HATCH_Z[0]))
    m.box((158, HX1), (-HY, -HY + HW_), (HATCH_Z[1], HZ1))
    m.box((178, HX1), (-HY, -HY + HW_), HATCH_Z)
    m.box((HX0, HX0 + HW_), (-HY, HY), (HZ0, HZ1))                      # затылок
    m.box((118, 132), (-16, 16), (THR_Z[1], HZ0 + HW_))                 # фланец на 51100
    m.cyl((NECK_Y.x, 0, (NECK_Y.z + 3.4 + THR_Z[1]) / 2), (0, 0, 1), 4.5,
          THR_Z[1] - NECK_Y.z - 3.4, 24)                                # втулка к качалке MG90S
    cut = Mesh()
    for ys in (1, -1):                                                   # звук к микрофонам
        for dx in (-3, 0, 3):
            cut.cyl((MIC[0] + dx, ys * (HY - HW_ / 2), MIC[2]), (0, 1, 0), 0.75, 4, 12)
    cut.box((130, 141), (HY - 4, HY + 1), (310, 316.5))                 # USB-C «Органов» (слева)
    for yc in (-24, -16, -8, 0, 8, 16, 24):                              # вентиляция «Мозга» в крышке
        cut.box((168, 175), (yc - 1.5, yc + 1.5), (HZ1 - HW_ - 1, HZ1 + 1))
    return m, cut


def build_head():
    shell, cut = _head_shell()
    rig.make("Head_shell", shell, col("Shell"), HEAD, bevel=1.5, cut=cut,
             props={"print_orientation": "затылком на стол"})
    m = Mesh().mat(M["dark"]).box((158.2, 177.8), (-HY, -HY + HW_), (HATCH_Z[0] + 0.2, HATCH_Z[1] - 0.2))
    rig.make("Head_service_hatch", m, col("Shell"), HEAD, bevel=0.6,
             props={"print_orientation": "плоско",
                    "access": "флешка (вдоль −Y, сечение 16 × 7 в окне 19.6 × 19.6) и USB-C «COM» «Мозга»"})
    m = Mesh().mat(M["shell"]).box((HX1, HX1 + 2.4), (-HY + 3, HY - 3), (296, HZ1 - 2))
    cut = Mesh()
    for ys in (1, -1):
        cut.cyl((HX1 + 1.2, ys * EYE_Y, EYE_Z), (1, 0, 0), 16.5, 5, 64)   # окна экранов Ø33
    cut.cyl((HX1 + 1.2, 0, EYE_Z), (1, 0, 0), 4.5, 5, 24)                   # окно камеры Ø9
    rig.make("Head_face", m, col("Shell"), HEAD, bevel=1.0, cut=cut,
             props={"print_orientation": "лицом на стол"})
    m = Mesh().mat(M["shell"]).box((181, 212), (-24, 24), (296, 310))
    rig.make("Head_muzzle", m, col("Shell"), HEAD, bevel=6.0)
    _jaw()
    _ears()
    _electronics()


def _jaw():
    # 18: MG90S в голове, вал +Y; ответная сторона — 2 × MR683ZZ на винте M3 из кронштейна
    place_servo(18, frame((JAW.x, 14, JAW.z), (0, 1, 0), (1, 0, 0)))
    m = Mesh().mat(M["accent"])
    m.cyl((JAW.x, 18.1, JAW.z), (0, 1, 0), 7, 1.8)
    m.stadium((JAW.x, JAW.z), (186, 286), 8, 5, (19, 21))
    m.ring((JAW.x, -20, JAW.z), (0, 1, 0), 6, 3.6, 6)                    # гнездо 2 × MR683 (Ø7.2)
    m.stadium((JAW.x + 8, JAW.z - 4.5), (186, 286), 5, 5, (-21, -19))
    # лоток динамика: дно с решёткой, борта
    m.mat(M["shell"]).box((181, 211), (-23.5, 23.5), (284, 286))
    for ys in (1, -1):
        m.box((181, 211), rng(21.5, 23.5, ys), (286, 294))
    m.box((209, 211), (-21.5, 21.5), (286, 294))
    m.box((181, 183), (-21.5, 21.5), (286, 294))
    cut = Mesh()
    for x in range(187, 207, 4):
        for y in range(-12, 13, 4):
            cut.cyl((x, y, 285), (0, 0, 1), 1.0, 4, 12)
    rig.make("Jaw", m, col("Structure/Head"), N[18], bevel=1.0, cut=cut,
             props={"print_orientation": "дном на стол", "loaded": True})
    boards.place("Speaker_35x25", "speaker", (196, 0, 290.8), (0, 0, -1), (0, 1, 0), "Senses", N[18],
                 "Speaker", {"mounted_on": ["Jaw"], "grille": "решётка 5 × 7 отверстий Ø2 в дне челюсти"})
    m = Mesh().mat(M["tpu"])
    for ys in (1, -1):
        m.box((183, 211), rng(23.5, 24.5, ys), (287, 294.8))
    m.box((211, 212), (-24.5, 24.5), (287, 294.8))
    rig.make("Jaw_lips_TPU", m, col("Structure/Head"), N[18],
             props={"print_orientation": "TPU 95A, плоско", "mounted_on": ["Jaw"]})
    m = Mesh().mat(M["tpu"])
    for y in (-14, -8.5, -3, 2.5, 8, 13.5):
        m.box((205.5, 209.5), (y, y + 3), (294, 295.6))
    rig.make("Jaw_teeth_TPU", m, col("Structure/Head"), N[18],
             props={"print_orientation": "TPU 95A, гребёнкой вверх", "mounted_on": ["Jaw"]})
    m = Mesh().mat(M["accent"]).box((165, 175), (-HY + HW_, -23.2), (292, 302))
    m.mat(M["steel"]).cyl((JAW.x, -21.75, JAW.z), (0, 1, 0), 1.5, 8.5, 16)      # винт M3
    rig.make("Jaw_bearing_arm", m, col("Structure/Head"), HEAD, bevel=0.6,
             props={"print_orientation": "боком на стол", "mounted_on": ["Head_shell"]})
    for i, y in enumerate((-21.5, -18.5)):
        bearing(f"Jaw_bearing_{i + 1}_MR683", "MR683ZZ", (JAW.x, y, JAW.z), (0, 1, 0), N[18], HEAD)


def _ears():
    # 19/20: уши, SG90 у боковых стенок, вал наружу (±Y)
    for no, ys, side in ((19, 1, "L"), (20, -1, "R")):
        place_servo(no, frame((EAR.x, ys * (HY - HW_), EAR.z), (0, ys, 0), (1, 0, 0)))
        m = Mesh().mat(M["accent"])
        m.cyl((EAR.x, ys * 48.5, EAR.z), (0, 1, 0), 7, 1.6)
        m.stadium((EAR.x, EAR.z), (EAR.x - 10, EAR.z + 36), 10, 4, rng(49.3, 51.8, ys))
        rig.make(f"Ear_{side}", m, col("Structure/Head"), N[no], bevel=1.0,
                 props={"print_orientation": "плоско"})


def _electronics():
    P_ = boards.place
    # «Органы чувств» плашмя, USB-C к левому борту (окно для кабеля)
    P_("ESP32_Senses", "devkitc1", SENSES_O, (0, 0, 1), (0, -1, 0), "Senses", HEAD, "ESP32_Senses",
       {"mounted_on": ["Head_shell"], "access": "USB-C через окно в левом борту"})
    # «Мозг» за глазами: модуль и разъём камеры к лицу, воздушный зазор ~10 мм до экранов,
    # USB-C вправо: COM — через лючок, USB/OTG — флешка
    P_("ESP32_Brain", "s3cam", BRAIN_O, (1, 0, 0), (0, 1, 0), "Brain", HEAD, "ESP32_Brain",
       {"mounted_on": ["Head_shell"], "usb_native": "USB-C «USB» (GPIO19/20, хост) — OTG к флешке",
        "usb_com": "USB-C «COM» (CH343) — через лючок на правом боку", "camera_flex": "штатный 21 мм"})
    P_("Camera_OV2640", "ov2640", (176.5, 0, EYE_Z), (1, 0, 0), (0, 1, 0), "Brain", HEAD, "ESP32_Brain",
       {"mounted_on": ["Head_face"], "flex": "24 pin, штатный ~21 мм"}, mass_g=1.5)
    P_("OTG_plug_USB_C_90", "otg_plug90", (BRAIN_O[0] + 3.25, -32.6, BRAIN_O[2] + 6.5), (1, 0, 0), (0, -1, 0),
       "Brain", HEAD, "OTG_cable", {"mounted_on": ["ESP32_Brain"]}, mass_g=3)
    P_("OTG_socket_USB_A", "otg_socket", (166.5, FLASH_Y + 12, FLASH_Z), (0, 0, 1), (0, 1, 0), "Brain", HEAD,
       "OTG_cable", {"mounted_on": ["Head_shell"]}, mass_g=4)
    P_("USB_flash_50GB", "usb_flash", (166.5, FLASH_Y, FLASH_Z), (0, 0, 1), (0, -1, 0), "Brain", HEAD,
       "USB_flash", {"mounted_on": ["OTG_socket_USB_A", "Head_shell"],
                     "access": "лючок на правом боку головы"})
    # дно головы: INA226, MAX98357A, 2 × SN65HVD230 — плашмя, провода пайкой
    for name, kind, o, key, extra in (
            ("INA226_jaw", "ina226", (130, -31.5, 291), "INA226_jaw", {}),
            ("Amp_MAX98357A", "max98357", (128, -8.5, 291), "Amp_MAX98357A", {}),
            ("CAN_transceiver_Senses", "sn65", (128, 10, 291), "CAN_transceiver", {"terminator": "оставить 120 Ом"}),
            ("CAN_transceiver_Brain", "sn65", (128, 27, 291), "CAN_transceiver", {"terminator": "снять"})):
        P_(name, kind, o, (0, 0, 1), (1, 0, 0), "Senses" if "Brain" not in name else "Brain", HEAD, key,
           {"mounted_on": ["Head_shell"], **extra})
    for side, ys in (("L", 1), ("R", -1)):
        P_(f"Eye_{side}_GC9A01", "gc9a01", (HX1 - 4.6, ys * EYE_Y, EYE_Z), (1, 0, 0), (0, 1, 0), "Senses",
           HEAD, "Eyes_GC9A01", {"mounted_on": ["Head_face"]})
        P_(f"Mic_INMP441_{side}", "inmp441", (MIC[0], ys * MIC[1], MIC[2]), (0, -ys, 0), (1, 0, 0), "Senses",
           HEAD, "Mics_INMP441", {"mounted_on": ["Head_shell"]})
    build_electronics(HEAD_BOX)


HEAD_BOX = {"Cap_head_2200uF": ("Power", (143, 163), (-43, -30.5), (296, 308.5), "pcb_k", HEAD, "Capacitors")}
