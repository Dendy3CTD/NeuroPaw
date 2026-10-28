"""Раскладка v6: размеры (мм), оси суставов, таблица 20 сервоприводов (params.json)."""
import json
import math
import os
import sys

from mathutils import Vector

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(BASE, "params.json")) as f:
    P = json.load(f)
sys.path.insert(0, os.path.join(BASE, "scripts"))
import v6_knee_linkage as KL  # noqa: E402

# ── корпус ────────────────────────────────────────────────────────────────────
B = P["body"]
BOT = B["bottom_z"]                       # 150
WALL = B["wall"]                          # 3 — нагруженные стенки (торцы, дно задней секции)
SKIN = P["print"]["wall_min"]             # 2.4 — ненагруженные: крышки, бока, дно передней
IN_BOT = BOT + WALL                       # 153
IN_TOP = BOT + B["height"] - WALL         # 217
TOP = IN_TOP + SKIN                       # 219.4 — верх крышки
HW = B["width"] / 2                       # 60
IN_W = HW - WALL                          # 57
GAP2 = B["spine_gap"] / 2                 # 15
END = GAP2 + B["section_length"]          # 135
WIN_Y, WIN_Z = 44.0, (156.0, 214.0)       # окно в торцах у позвоночника

# ── ноги ──────────────────────────────────────────────────────────────────────
AXIS_Z = P["stance"]["hip_axis_z"]        # 175
SH_X = END - WALL - 3.0                   # 129 — основание вала плечевой сервы (6802 в стенке)
SH_Y = P["shoulder_spacing"]["across_body"] / 2   # 45
HX = P["shoulder_spacing"]["along_body"] / 2      # 110
UL, LL = P["leg"]["upper_length"], P["leg"]["lower_length"]
FOOT_R = P["leg"]["foot_diameter"] / 2
MG_DEPTH = 38.9                           # корпус MG996R ниже основания вала
HIP_Y0 = HW + 10.0                        # 70 — внутренняя грань сервы бедра
SHAFT_Y = HIP_Y0 + MG_DEPTH               # 108.9
PLATE_OUT = (SHAFT_Y + 4.0, SHAFT_Y + 7.2)   # нагруженная щека 3.2 мм
PLATE_IN = (61.8, 65.0)                   # внутренняя щека бедра 3.2 мм
BOSS_IN = (61.5, 66.0)                    # бобышка F625ZZ во внутренней щеке
CAP_Y = (66.5, 69.5)                      # крышка на дне сервы бедра с осью Ø5
LEG_Y = (HIP_Y0 + SHAFT_Y) / 2            # 89.45
LINK_Y = (PLATE_OUT[1] + 0.5, PLATE_OUT[1] + 3.0)
ROD_Y = LINK_Y[1] + 1.5

# ── колено: четырёхзвенник (scripts/v6_knee_linkage.py) ───────────────────────
KN = P["knee_linkage"]
R1, R2, ROD_L = KN["r1"], KN["r2"], KN["rod_L"]
BETA = math.radians(KN["beta_deg"])
KNEE_SERVO_D, KNEE_U = KN["servo_d"], KN["servo_u"]
KAPPA = (KN["kappa_min"], KN["kappa_max"])
KNEE_TOGGLE = 130.04                       # мёртвая точка четырёхзвенника B (качалка и тяга в линию)
KNEE_STOP = 128.5                          # механический упор: 1.5° до мёртвой точки (допуск печати ±1°)
KNEE_WORK_MAX = 128.0                      # программный предел сервы

D_HF = AXIS_Z - FOOT_R
STAND_HIP = math.degrees(math.acos((UL**2 + D_HF**2 - LL**2) / (2 * UL * D_HF)))
_kx = -UL * math.sin(math.radians(STAND_HIP))
_kz = -UL * math.cos(math.radians(STAND_HIP))
STAND_KNEE = math.degrees(math.atan2(_kx, -(-D_HF - _kz))) - STAND_HIP   # φ = −κ


def _branch():
    """Ветка решения качалки (знак при acos) и её угол в стойке."""
    pts = KL.evaluate(R1, R2, BETA, ROD_L, KNEE_U, KAPPA[0], KAPPA[1], 1.0)
    k = -STAND_KNEE
    a_st = min(pts, key=lambda p: abs(p[0] - k))[1]
    t = KL.lever_tip(R2, BETA, k)
    du, dw = t[0] - KNEE_U, t[1] + KNEE_SERVO_D
    th = math.atan2(dw, du)
    return (1 if math.remainder(a_st - th, 2 * math.pi) > 0 else -1), a_st


KNEE_SIGMA, HORN_A0 = _branch()


def horn_expr():
    """Выражение драйвера (< 256 символов): поворот качалки ψ по углу колена k (рад).

    q = β − k — угол рычага; D = T − S = (r2·cos q − u_s, r2·sin q − h), h = UL − d_s;
    d² = r2² + u_s² + h² − 2·r2·(u_s·cos q + h·sin q);
    α = atan2(D) + σ·acos((r1² − L² + d²) / (2·r1·d));  ψ = α0 − α.
    """
    h = UL - KNEE_SERVO_D
    q = f"({BETA:.4f}-k)"
    c0 = R2**2 + KNEE_U**2 + h**2
    lin = f"-{2 * R2 * h:g}*sin{q}" + (f"-{2 * R2 * KNEE_U:g}*cos{q}" if KNEE_U else "")
    d2 = f"{c0:g}{lin}"
    num = f"{R1**2 - ROD_L**2 + c0:g}{lin}"
    du = f"{R2:g}*cos{q}" + (f"-{KNEE_U:g}" if KNEE_U else "")
    sig = "+" if KNEE_SIGMA > 0 else "-"
    return (f"{HORN_A0:.4f}-(atan2({R2:g}*sin{q}-{h:g},{du}){sig}"
            f"acos(min(1,max(-1,({num})/({2 * R1:g}*sqrt({d2}))))))")


LEGS = {"FL": (1, 1, 1), "FR": (1, -1, 4), "BL": (-1, 1, 7), "BR": (-1, -1, 10)}

# ── позвоночник, шея, голова, хвост ───────────────────────────────────────────
SP_P = Vector((B["spine_pitch_axis"]["x"], 0, B["spine_pitch_axis"]["z"]))   # (−29, 0, 191)
SP_Y = Vector((B["spine_yaw_axis"]["x"], 0, 185))                           # (24, 0, …)
NECK_P = Vector((120, 0, 234))
NECK_Y = Vector((120, 0, 277))             # MG90S ниже на 8 мм: над ней упорный 51100
JAW = Vector((170, 0, 297))
EAR = Vector((150, 47, 334))
TAIL = Vector((-148, 0, 210))

# ── 20 сервоприводов из params.json: (№, имя, сустав, тип, ход, плата, канал, питание)
SERVOS = [(s["no"], s["name"], s["joint"], s["type"], tuple(s["range"]), s["board"],
           s["channel"], s["power"]) for s in P["servo_table"]]
SERVO_BY_NO = {s[0]: s for s in SERVOS}
N = {s[0]: s[1] for s in SERVOS}          # № → имя кости/объекта


def bones():
    """[(имя, голова, ось, родитель)] — порядок: родитель раньше ребёнка."""
    out = [("Root", (-75, 0, 185), (0, 1, 0), None),
           (N[14], tuple(SP_P), (0, 1, 0), "Root"),
           (N[13], tuple(SP_Y), (0, 0, 1), N[14])]
    for leg, (xs, ys, n0) in LEGS.items():
        parent = N[13] if xs > 0 else "Root"
        a, h, k = N[n0], N[n0 + 1], N[n0 + 2]
        hx = xs * HX
        tip = (hx + R2 * math.cos(BETA), ys * ROD_Y, AXIS_Z - UL + R2 * math.sin(BETA))
        out += [(a, (xs * SH_X, ys * SH_Y, AXIS_Z), (1, 0, 0), parent),
                (h, (hx, ys * LEG_Y, AXIS_Z), (0, 1, 0), a),
                (k, (hx, ys * LEG_Y, AXIS_Z - UL), (0, 1, 0), h),
                (f"MCH_{leg}_knee_horn", (hx + KNEE_U, ys * LEG_Y, AXIS_Z - KNEE_SERVO_D),
                 (0, 1, 0), h),
                (f"MCH_{leg}_rod_tip", tip, (0, 1, 0), k)]
    out += [(N[16], tuple(NECK_P), (0, 1, 0), N[13]),
            (N[17], tuple(NECK_Y), (0, 0, 1), N[16]),
            (N[18], tuple(JAW), (0, 1, 0), N[17]),
            (N[19], tuple(EAR), (0, 1, 0), N[17]),
            (N[20], (EAR.x, -EAR.y, EAR.z), (0, 1, 0), N[17]),
            (N[15], tuple(TAIL), (0, 1, 0), "Root")]
    return out


def stand_pose():
    pose = {}
    for leg, (xs, ys, n0) in LEGS.items():
        pose[N[n0 + 1]] = STAND_HIP
        pose[N[n0 + 2]] = STAND_KNEE
    return pose
