"""
NeuroPaw — v6_knee_linkage.py
Кинематика четырёхзвенника колена: серва в бедре → качалка r1 → тяга L → рычаг r2 на голени.
Перебор геометрии под разные диапазоны колена, таблица с шагом 5°,
результат → docs/knee_linkage.md и params.json["knee_linkage"].

Система координат бедра (мм): u — вперёд ⟂ бедру, w — вдоль бедра к тазу.
Ось бедра (0, 0), вал коленной сервы S = (u_s, −40), ось колена K = (0, −110).
Колено: φ — поворот голени (как у кости), сгибание κ = −φ (колено назад).
Запуск: python3 scripts/v6_knee_linkage.py
"""
import json
import math
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UL, S_D = 110.0, 40.0
SERVO_SPAN = 170.0          # используемый ход MG996R (500–2500 мкс), °
MU_MIN = 30.0               # минимальный угол передачи (тяга ↔ рычаг), °
PIN_CLEAR = 6.0             # тяга не ближе 6 мм к осям S и K
STANCE = (75, 110)          # стойка и шаг — где нужна максимальная передача
R1 = 15.0                   # качалка 25T ~15 мм (по ТЗ)


def rot(v, phi):
    x, z = v
    return (x * math.cos(phi) + z * math.sin(phi), -x * math.sin(phi) + z * math.cos(phi))


def lever_tip(r2, beta, kappa):
    """Конец рычага на голени при сгибании κ (°)."""
    d = rot((math.cos(beta), math.sin(beta)), math.radians(-kappa))
    return (r2 * d[0], -UL + r2 * d[1])


def horn_angle(s, r1, t, L, prev):
    """Угол качалки α: пересечение окружностей (S, r1) и (T, L); ветка ближе к prev."""
    dx, dz = t[0] - s[0], t[1] - s[1]
    d = math.hypot(dx, dz)
    if d > r1 + L or d < abs(L - r1) or d == 0:
        return None
    a = (r1 * r1 - L * L + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0))
    mx, mz = s[0] + a * dx / d, s[1] + a * dz / d
    sols = [math.atan2(mz + k * h * dx / d - s[1], mx - k * h * dz / d - s[0]) for k in (1, -1)]
    if prev is None:
        return sols
    return min(sols, key=lambda x: abs(math.remainder(x - prev, 2 * math.pi)))


def seg_dist(p, a, b):
    ax, az = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((p[0] - a[0]) * ax + (p[1] - a[1]) * az) / (ax * ax + az * az)))
    return math.hypot(a[0] + t * ax - p[0], a[1] + t * az - p[1])


def evaluate(r1, r2, beta, L, us, k_lo, k_hi, step=1.0):
    """Ход κ ∈ [k_lo, k_hi]: список точек или None, если не собирается/не проходит."""
    s, kp = (us, -S_D), (0.0, -UL)
    best = None
    for start in (0, 1):
        pts, prev = [], None
        k = k_lo
        ok = True
        while k <= k_hi + 1e-9:
            t = lever_tip(r2, beta, k)
            a = horn_angle(s, r1, t, L, prev)
            if a is None:
                ok = False
                break
            if prev is None:
                a = a[start]
            h = (s[0] + r1 * math.cos(a), s[1] + r1 * math.sin(a))
            rx, rz = h[0] - t[0], h[1] - t[1]
            lx, lz = t[0] - kp[0], t[1] - kp[1]
            mu = math.degrees(math.asin(min(1, abs(lx * rz - lz * rx) / (r2 * L))))
            if mu < MU_MIN or seg_dist(kp, h, t) < PIN_CLEAR or seg_dist(s, h, t) < PIN_CLEAR:
                ok = False
                break
            pts.append([k, a, mu])
            prev = a
            k += step
        if not ok:
            continue
        span = abs(math.degrees(math.remainder(pts[-1][1] - pts[0][1], 2 * math.pi)))
        if span > SERVO_SPAN:
            continue
        for i, p in enumerate(pts):          # передача dα/dκ
            j0, j1 = max(i - 1, 0), min(i + 1, len(pts) - 1)
            da = math.degrees(math.remainder(pts[j1][1] - pts[j0][1], 2 * math.pi))
            p.append(abs(da) / ((pts[j1][0] - pts[j0][0]) or 1))
        if best is None or score(pts) > score(best):
            best = pts
    return best


def score(pts):
    return min(p[3] for p in pts if STANCE[0] <= p[0] <= STANCE[1])


def search(k_lo, k_hi, r1=R1, offsets=(0.0,)):
    """Мелкая сетка: r2 24–30 мм шаг 1, β шаг 2°, L 45–95 мм шаг 1, смещение сервы."""
    best = None
    for us in offsets:
        for r2 in range(24, 31):
            for beta_d in range(0, 360, 2):
                for L in range(45, 96):
                    pts = evaluate(r1, float(r2), math.radians(beta_d), float(L), us, k_lo, k_hi, 2.5)
                    if pts and (best is None or score(pts) > best[0]):
                        best = (score(pts), (r1, float(r2), beta_d, float(L), us))
    return best


def stance_kappa():
    d = 175 - 10.0
    a = math.acos((UL**2 + d**2 - 120.0**2) / (2 * UL * d))
    kx, kz = -UL * math.sin(a), -UL * math.cos(a)
    return -(math.degrees(math.atan2(kx, -(-d - kz))) - math.degrees(a))


# ── позы: сила на стопу (доля веса), сгибание κ, плечо колена (мм) ──────────────
def knee_lever(hip_z, foot_dx, foot_z=10.0, l2=120.0):
    """Плечо колена = |x_колена − x_стопы| при колене назад; foot_dx — стопа от бедра по X."""
    fx, fz = foot_dx, foot_z - hip_z
    d = math.hypot(fx, fz)
    a = math.acos((UL**2 + d**2 - l2**2) / (2 * UL * d))
    base = math.atan2(fz, fx)
    kx = UL * math.cos(base - a)           # колено с «задней» стороны
    kz = UL * math.sin(base - a)
    if kx > UL * math.cos(base + a):
        kx, kz = UL * math.cos(base + a), UL * math.sin(base + a)
    inner = math.degrees(math.acos((UL**2 + l2**2 - d**2) / (2 * UL * l2)))
    return abs(kx - fx), 180 - inner


def poses(mass_kg):
    """[(поза, доля веса на ногу, коэф. динамики, высота бедра, стопа dx)]"""
    return [
        ("стоит, 4 ноги", 0.25, 1.0, 175, 0),
        ("рысь, 2 диагональные ноги", 0.50, 1.0, 175, 0),
        ("рысь, ×1.3 динамика", 0.50, 1.3, 175, 0),
        ("шаг, 3 ноги, стопа вынесена на 40 мм", 0.51, 1.0, 175, 40),
        ("высокая стойка (бедро 200 мм)", 0.25, 1.0, 200, 0),
        ("встаёт из «лежит» (бедро 90°, живот 77 мм над полом), ×1.3", 0.25, 1.3, 102, -33),
        ("лежит (нижнее положение)", 0.25, 1.0, 102, -33),
    ]


MG996R_TORQUE, MG996R_SPEED = 11.0, 60 / 0.14     # кг·см и °/с при 6 В


def ratio_at(pts, k):
    return min(pts, key=lambda p: abs(p[0] - k))[3]


def report(geom, lo, hi, mass_kg):
    r1, r2, bd, L, us = geom
    pts = evaluate(r1, r2, math.radians(bd), L, us, lo, hi, 1.0)
    a0 = pts[0][1]
    rows = []
    for p in pts:
        if (p[0] - lo) % 5 == 0:
            alpha = math.degrees(math.remainder(p[1] - a0, 2 * math.pi))
            rows.append(f"| {p[0]:.0f} | {alpha:+.1f} | {p[3]:.2f} | {p[2]:.0f} | "
                        f"{MG996R_SPEED / p[3]:.0f} |")
    pose_rows = []
    worst = 99
    for name, share, dyn, hz, dx in poses(mass_kg):
        lever, kappa = knee_lever(hz, dx)
        if not lo <= kappa <= hi:
            pose_rows.append(f"| {name} | {kappa:.0f} | — | — | — | вне хода |")
            continue
        joint = mass_kg * share * dyn * lever / 10
        rt = ratio_at(pts, kappa)
        m = MG996R_TORQUE / (joint / rt) if joint > 0 else 99
        worst = min(worst, m) if "лежит," not in name else worst
        flag = "" if m >= 1.8 else " ⚠"
        pose_rows.append(f"| {name} | {kappa:.0f} | {lever:.0f} | {joint:.1f} | {rt:.2f} | {m:.1f}{flag} |")
    span = abs(math.degrees(math.remainder(pts[-1][1] - pts[0][1], 2 * math.pi)))
    return pts, rows, pose_rows, span, worst


if __name__ == "__main__":
    MASS = 2.3
    variants = [("B — выбран: 65…130°", 15.0, 65, 130, (0.0,)),
                ("A — только стойка/шаг: 65…110°", 15.0, 65, 110, (0.0,)),
                ("C1 — до 140°", 15.0, 65, 140, (0.0, -4.0, 4.0)),
                ("C2 — до 145° (сидит по-собачьи), качалка 18 мм", 18.0, 60, 145, (0.0, -4.0, 4.0))]
    found = {}
    for name, r1, lo, hi, offs in variants:
        b = search(lo, hi, r1, offs)
        found[name] = (b, lo, hi)
        print(f"[knee] {name}: " + ("нет решения" if b is None else
              f"передача ≥ {b[0]:.2f}; r1={b[1][0]} r2={b[1][1]} β={b[1][2]}° L={b[1][3]} u_s={b[1][4]}"))
    name = variants[0][0]
    (sc, geom), lo, hi = found[name]
    pts, rows, pose_rows, span, worst = report(geom, lo, hi, MASS)
    lever_st, kappa_st = knee_lever(175, 0)
    md = ["# Колено: рычажная передача (четырёхзвенник)", "",
          "Источник: `scripts/v6_knee_linkage.py`. Масса робота в расчёте — "
          f"{MASS} кг (цель), момент MG996R {MG996R_TORQUE} кг·см и {MG996R_SPEED:.0f}°/с при 6 В.", "",
          "## Схема", "",
          "Серва колена стоит в бедре, вал в 40 мм от оси бедра, ось колена в 110 мм.",
          "Качалка r1 соединена с рычагом r2 на голени тягой L на двух шаровых наконечниках M3.",
          "κ — сгибание колена (0 = прямая нога, колено назад), β — угол рычага от поперечной оси голени при κ = 0, α — угол качалки от положения при κ = "
          f"{lo}°.", "",
          f"**Выбранная геометрия (B):** r1 = {geom[0]:.0f} мм, r2 = {geom[1]:.0f} мм, "
          f"тяга L = {geom[3]:.0f} мм (между центрами шаров), рычаг повёрнут на β = {geom[2]}° "
          f"от оси голени, вал сервы на оси бедра (u_s = {geom[4]:.0f}).", "",
          f"- Ход колена **κ = {lo}…{hi}°** ({hi - lo}°) при ходе сервы **{span:.0f}°** "
          f"(лимит {SERVO_SPAN:.0f}°: импульс 500–2500 мкс).",
          f"- Передача в зоне стойки и шага (κ {STANCE[0]}–{STANCE[1]}°): **≥ {sc:.2f}**, "
          f"в стойке (κ = {kappa_st:.0f}°): **{ratio_at(pts, kappa_st):.2f}**.",
          f"- Угол передачи на всём ходе ≥ {min(p[2] for p in pts):.0f}° (требование ≥ {MU_MIN:.0f}°), "
          "тяга не подходит к осям ближе 6 мм.", "",
          "## Сравнение вариантов (ход ↔ передача)", "",
          "| Вариант | Ход κ | Мин. передача в стойке/шаге | Геометрия r1/r2/L |", "|---|---|---:|---|"]
    for n, (b, l, h) in found.items():
        md.append(f"| {n} | {l}–{h}° | " + ("нет решения |  |" if b is None else
                  f"{b[0]:.2f} | {b[1][0]:.0f}/{b[1][1]:.0f}/{b[1][3]:.0f} мм |"))
    md += ["", "## Таблица хода (шаг 5°)", "",
           "| κ, ° | α сервы, ° | Передача | Угол передачи, ° | Скорость колена, °/с |",
           "|---:|---:|---:|---:|---:|"] + rows
    md += ["", "## Позы «лежит», «встаёт», «сидит»", "",
           "Проверено на модели (`scripts/v6_poses.py`): пересечений нет, тяга замкнута.", "",
           "- **«Лежит» = нижнее положение**: бедро 90° (горизонтально назад), колено 130°, "
           "ось бедра 102 мм, живот **77 мм над полом**.",
           "- **Лечь животом на пол нельзя**: нужно бедро ≈ 150° (стопа позади бедра, колено вверх-назад). "
           "Таблица даёт ±90°, а механически при ≈ 138° коленная серва упирается в серву бедра.",
           "  Если живот на полу обязателен: сместить ноль бедра (ход −30…+150°) и опустить коленную "
           "серву в бедре на ~12 мм (новый расчёт рычагов), перенести верхнюю планку кронштейна.",
           "- **«Встаёт»** начинается из нижнего положения: передача у κ = 130° ≈ 10 (рядом с мёртвой "
           "точкой качалки), колено медленное (~40°/с), но момент с большим запасом.",
           "- **«Сидит»**: задние ноги в нижнем положении (ось бедра 102 мм), передние в высокой стойке "
           "(204 мм) → наклон корпуса ≈ 28°, плюс позвоночник до 20°. Таз до пола не достаёт (~70 мм).",
           "- ⚠ У κ = 130° качалка почти на одной линии с тягой: нужен **механический упор на 131–132°**, "
           "иначе при падении механизм может проскочить мёртвую точку и вывернуться.", "",
           f"## Запас по моменту колена (MG996R {MG996R_TORQUE} кг·см)", "",
           "| Поза | κ, ° | Плечо, мм | Момент в колене, кг·см | Передача | Запас |",
           "|---|---:|---:|---:|---:|---:|"] + pose_rows
    with open(os.path.join(BASE, "docs", "knee_linkage.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(BASE, "params.json")) as f:
        P = json.load(f)
    P["knee_linkage"] = {"r1": geom[0], "r2": geom[1], "beta_deg": geom[2], "rod_L": geom[3],
                         "servo_u": geom[4], "servo_d": S_D, "kappa_min": lo, "kappa_max": hi,
                         "ratio_stance": round(ratio_at(pts, kappa_st), 3),
                         "ratio_min_walk": round(sc, 3), "servo_span_deg": round(span, 1)}
    with open(os.path.join(BASE, "params.json"), "w") as f:
        json.dump(P, f, ensure_ascii=False, indent=2)
    print("\n".join(md))
