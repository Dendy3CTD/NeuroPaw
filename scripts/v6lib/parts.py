"""Общие материалы и установка сервоприводов с метаданными."""
from . import rig, servo
from .geom import Mesh, col, mat
from .layout import P, SERVO_BY_NO

M = {
    "shell": mat("PETG_white", (0.85, 0.86, 0.84), 0.42),
    "accent": mat("PETG_orange", (0.95, 0.33, 0.05), 0.4),
    "dark": mat("PETG_graphite", (0.06, 0.06, 0.07), 0.45),
    "horn": mat("Horn_aluminium", (0.78, 0.79, 0.8), 0.3, 1.0),
    "tpu": mat("TPU_black", (0.03, 0.03, 0.03), 0.9),
    "steel": mat("Steel", (0.75, 0.75, 0.77), 0.28, 1.0),
    "pcb_g": mat("PCB_green", (0.02, 0.22, 0.08), 0.5),
    "pcb_b": mat("PCB_blue", (0.02, 0.07, 0.35), 0.5),
    "pcb_k": mat("PCB_black", (0.03, 0.03, 0.035), 0.45),
    "bat": mat("Battery_wrap", (0.1, 0.35, 0.2), 0.6),
    "glass": mat("Face_glass", (0.005, 0.005, 0.008), 0.06),
    "eye": mat("Eye_LED", (0.15, 0.75, 1.0), 0.3, emit=4.0),
    "lens": mat("Lens", (0.02, 0.03, 0.05), 0.05, 0.6),
    "can": mat("CAN_cable", (0.95, 0.85, 0.1), 0.5),
    "gold": mat("Connector_gold", (0.9, 0.7, 0.3), 0.3, 1.0),
}

TYPE_COL = {t: f"Servos/{t}" for t in ("MG996R", "DS3235MG", "MG90S", "SG90")}


def place_servo(no, m):
    """Ставит серву №no по матрице m (geom.frame) на звено-родитель её кости."""
    n, name, joint, kind, rr, board, channel, power = SERVO_BY_NO[no]
    bone = rig.ARM.data.bones[name]
    link = bone.parent.name
    mesh = servo.build(Mesh(), kind, m)
    sp = P["servos"][kind]
    o = rig.make(name, mesh, col(TYPE_COL[kind]), link, origin=m.translation,
                 props={"servo_no": n, "servo_type": kind, "joint": joint,
                        "range_deg": list(rr), "board": board, "channel": channel,
                        "power": power, "torque_kgcm": sp["torque_kgcm"],
                        "mass_g": sp["mass_g"], "drives_bone": name,
                        "shaft_sign": 1 if (m.col[2].xyz @ bone.vector.normalized()) > 0 else -1})
    return o
