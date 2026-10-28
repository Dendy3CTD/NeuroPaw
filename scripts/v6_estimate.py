"""
NeuroPaw — v6_estimate.py
Предварительная оценка v6 (до построения модели): масса, центр масс по X,
моменты в суставах в худших позах, токи, время работы.
Точный расчёт по геометрии — на этапе 3 (scripts/v6_calc_*.py).
Запуск: python3 scripts/v6_estimate.py  → docs/estimate_v6_prelim.md
"""
import json
import math
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(BASE, "params.json")) as f:
    P = json.load(f)

G = 9.81
UL, LL = P["leg"]["upper_length"], P["leg"]["lower_length"]
HIP_X = P["shoulder_spacing"]["along_body"] / 2
HIP_Z = P["stance"]["hip_axis_z"]
FOOT_R = P["leg"]["foot_diameter"] / 2
SERVO = P["servos"]

# ── массы: (название, г, x мм) — x нужен для центра масс по длине ─────────────
# Пластик PETG оценён по площади стенок × толщина (тонкие стенки печатаются
# сплошными) + рёбра; заполнение 40 % — для толстых деталей (кронштейны).
LEGS = [("FL", 1), ("FR", 1), ("BL", -1), ("BR", -1)]
M = []
for leg, s in LEGS:
    x = s * HIP_X
    M += [
        (f"{leg}: 3 × MG996R (01–12)", 3 * SERVO["MG996R"]["mass_g"], x),
        (f"{leg}: кронштейн плеча PETG", 28, x + s * 10),
        (f"{leg}: бедро (2 щеки + накладка) PETG", 45, x - 40),
        (f"{leg}: голень + накладка PETG", 24, x),
        (f"{leg}: стопа TPU", 9, x),
        (f"{leg}: 3 подшипника F625ZZ + оси", 3 * 4.5 + 3 * 3, x),
        (f"{leg}: 3 качалки 25T Al + тяга M3 + 2 шаровых", 3 * 6 + 4 + 2 * 2.5, x - 30),
    ]
BODY = [
    ("Передняя секция PETG (2.4–3.2 мм)", 175, 75),
    ("Задняя секция PETG + крышка отсека АКБ", 190, -75),
    ("Узел позвоночника: вилка + 2 × 6802ZZ", 55, 0),
    ("Сильфон позвоночника TPU", 18, 0),
    ("13 spine_pitch MG996R", SERVO["MG996R"]["mass_g"], -27),
    ("14 spine_yaw MG996R", SERVO["MG996R"]["mass_g"], 18),
    ("15 neck_pitch MG996R + основание шеи", SERVO["MG996R"]["mass_g"] + 25, 118),
    ("16 neck_yaw MG90S + звено шеи + 6802ZZ", SERVO["MG90S"]["mass_g"] + 20 + 6, 135),
    ("Голова PETG (оболочка, морда, челюсть, уши)", 95, 175),
    ("17–19 jaw/ear SG90 × 3", 3 * SERVO["SG90"]["mass_g"], 175),
    ("Хвост PETG + 20 SG90", 15 + SERVO["SG90"]["mass_g"], -150),
    ("Крепёж M3/M2.5 + термовставки (~140 шт.)", 70, 0),
]
E = P["electronics"]
ELEC = [(f"{k}", v["mass_g"], v["x"]) for k, v in E.items()]
ELEC.append(("Провода: 20 жгутов сервоприводов, CAN, силовые", 85, -10))
ITEMS = M + BODY + ELEC

total = sum(m for _, m, _ in ITEMS)
com_x = sum(m * x for _, m, x in ITEMS) / total
mg = total / 1000  # кг

# ── моменты ───────────────────────────────────────────────────────────────────
def stance(hip_z):
    """Стопа под осью бедра, колено назад: угол бедра и плечо колена (мм)."""
    d = hip_z - FOOT_R
    a = math.acos((UL**2 + d**2 - LL**2) / (2 * UL * d))
    return a, UL * math.sin(a)


a_nom, knee_lever = stance(HIP_Z)
_, knee_lever_tall = stance(HIP_Z + 25)

# Три ноги: CoM смещён в опорный треугольник на 10 мм → нагрузка на ноги
y_foot = P["leg"]["foot_y"]
w_front = (HIP_X + com_x) / (2 * HIP_X)
# FR несёт долю передних, BL и BR — задних; решаем 3 уравнения равновесия
dy = -10.0
w_fr = w_front                    # из баланса по X (FL поднята)
w_bl_minus_br = (dy + y_foot * w_fr) / y_foot
w_bl = ((1 - w_fr) + w_bl_minus_br) / 2
w_br = 1 - w_fr - w_bl
leg3 = max(w_fr, w_bl) * mg      # кг на самую нагруженную ногу

abd_off = (P["leg"]["foot_y"] - P["shoulder_spacing"]["across_body"] / 2) / 10   # см
DYN = 1.3   # динамический коэффициент при вставании


def row(n, name, typ, need, note):
    t = SERVO[typ]["torque_kgcm"]
    k = t / need if need > 0 else float("inf")
    flag = "" if k >= 1.5 else " ⚠"
    return f"| {n} | {name} | {typ} | {need:.2f} | {t:.1f} | {k:.1f}{flag} | {note} |"


head_m = (95 + SERVO["MG90S"]["mass_g"] + 3 * SERVO["SG90"]["mass_g"]
          + sum(v["mass_g"] for k, v in E.items() if v["x"] > 140)) / 1000

T = [
    row("03/06/09/12", "колено, 3 ноги", "MG996R", leg3 * knee_lever / 10,
        f"{leg3:.2f} кг × {knee_lever / 10:.1f} см, высота бедра {HIP_Z} мм"),
    row("", "колено, 3 ноги, стойка выше на 25 мм", "MG996R", leg3 * knee_lever_tall / 10,
        f"плечо {knee_lever_tall / 10:.1f} см"),
    row("", "колено, 3 ноги — DS3218MG", "DS3218MG", leg3 * knee_lever / 10, "замена"),
    row("", "колено, 4 ноги, стоит", "MG996R", mg / 4 * knee_lever / 10, ""),
    row("", "колено, вставание: стопа под бедром", "MG996R", mg / 4 * UL / 10 * DYN,
        f"бедро горизонтально, плечо {UL / 10:.0f} см, ×{DYN}"),
    row("", "колено, вставание: стопа между бедром и коленом", "MG996R",
        mg / 4 * UL / 20 * DYN, "плечо 5.5 см — так и надо вставать"),
    row("02/05/08/11", "бедро, вставание (та же стратегия)", "MG996R", mg / 4 * UL / 20 * DYN, ""),
    row("", "бедро, 3 ноги, стопа сдвинута на 40 мм", "MG996R", leg3 * 4.0, ""),
    row("01/04/07/10", "отведение, 3 ноги", "MG996R", leg3 * abd_off,
        f"стопа в {abd_off * 10:.1f} мм от оси отведения"),
]

# позвоночник: изгибающий момент в узле при стойке на 4 ногах
front_nonleg = [(m, x) for n, m, x in BODY + ELEC if x > 0]
legs_front = sum(m for n, m, x in M if x > 0)
W_front = total * (HIP_X + com_x) / (2 * HIP_X)
spine_m = ((W_front - legs_front) * HIP_X - sum(m * x for m, x in front_nonleg)) / 1000 / 10
T.append(row("13", "позвоночник pitch, стоит", "MG996R", abs(spine_m) * 1.5,
             "изгиб в середине «балки» × 1.5 (шаг)"))
T.append(row("14", "позвоночник yaw, рысь", "MG996R", 1.2, "оценка: боковые силы стоп"))
T.append(row("15", "шея pitch, голова вперёд + игрушка 50 г", "MG996R",
             head_m * 7 + 0.05 * 12, f"голова {head_m:.2f} кг × 7 см"))
T.append(row("16", "шея yaw, шея наклонена 45°", "MG90S", head_m * 2 * 0.71 + 0.1, "+ инерция"))
T.append(row("17", "челюсть: игрушка 50 г + сжатие", "SG90", 0.05 * 5 + 0.25, ""))
T.append(row("18/19", "ухо 8 г", "SG90", 0.008 * 2.5, ""))
T.append(row("20", "хвост 20 г", "SG90", 0.02 * 5, ""))

# ── токи и время работы ───────────────────────────────────────────────────────
PW = P["power"]
servo_peak = 12 * 0.7 * SERVO["MG996R"]["stall_a"] + 3 * 0.5 * SERVO["MG996R"]["stall_a"] + 1.0
servo_walk = 12 * 0.5 + 2 * 0.3 + 0.5
servo_stand = 12 * 0.25 + 0.4
servo_idle = 20 * 0.01
logic_peak = sum(v.get("i_peak_a", 0) for v in E.values())
logic_avg = sum(v.get("i_avg_a", 0) for v in E.values())
bat_wh = PW["battery"]["voltage_nom"] * PW["battery"]["capacity_mah"] / 1000
usable = bat_wh * 0.8


def runtime(i_servo, i_logic):
    w = i_servo * 6.0 / 0.9 + i_logic * 5.0 / 0.9
    return w, usable / w * 60


lines = ["# NeuroPaw v6 — предварительная оценка (до модели)", "",
         "Источник: `scripts/v6_estimate.py`, параметры — `params.json`.",
         "Точные массы по геометрии — на этапе 3.", "",
         f"## Масса: **{total / 1000:.2f} кг**, центр масс по X: **{com_x:+.1f} мм** "
         f"(0 = середина между бёдрами, + = к голове)", "",
         "| Узел | г |", "|---|---:|"]
groups = {"Ноги (4 шт.)": sum(m for _, m, _ in M), "Корпус, позвоночник, шея, голова, хвост":
          sum(m for _, m, _ in BODY), "Электроника и провода": sum(m for _, m, _ in ELEC)}
lines += [f"| {k} | {v:.0f} |" for k, v in groups.items()]
lines += ["", "<details><summary>Электроника по позициям</summary>", "",
          "| Позиция | г | x, мм |", "|---|---:|---:|"]
lines += [f"| {n} | {m:.1f} | {x:+.0f} |" for n, m, x in ELEC]
lines += ["", "</details>", "",
          "## Моменты в худших позах (кг·см, момент сервы при 6 В)", "",
          f"Стойка: ось бедра {HIP_Z} мм, угол бедра {math.degrees(a_nom):.1f}°, "
          f"плечо колена {knee_lever:.0f} мм. Три ноги: поднята FL, центр масс смещён на 10 мм "
          f"в треугольник → FR {w_fr:.0%}, BL {w_bl:.0%}, BR {w_br:.0%} веса.", "",
          "| № | Поза | Серво | Нужно | Есть | Запас | Примечание |",
          "|---|---|---|---:|---:|---:|---|"] + T
lines += ["", "## Токи и время работы", "",
          f"- Сервоприводы, пик (вставание, 12 ног × 70 % stall + остальные): **{servo_peak:.1f} А** "
          f"при 6 В — UBEC {PW['ubec']['current_a']} А.",
          f"- Логика 5 В: пик **{logic_peak:.2f} А**, среднее {logic_avg:.2f} А — "
          f"DC-DC {PW['dcdc_logic']['current_a']} А.",
          f"- Аккумулятор: {bat_wh:.1f} Вт·ч, используем 80 % = {usable:.1f} Вт·ч."]
for name, i in (("ходьба", servo_walk), ("стоит", servo_stand), ("лежит, сервы держат минимум", servo_idle)):
    w, t = runtime(i, logic_avg)
    lines.append(f"- {name}: сервы {i:.1f} А → {w:.0f} Вт от батареи → **≈ {t:.0f} мин**")

out = os.path.join(BASE, "docs", "estimate_v6_prelim.md")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
