"""
NeuroPaw — v6_knee_spring.py
Торсионная пружина колена: помогает разгибать колено (держит вес), а при сгибании
и в переносе ноги серва работает против неё. Подбор проволоки, витков, диаметра и угла
предварительной закрутки так, чтобы запас сервы был ≥ 1.8 во ВСЕХ позах.
Вызывается из v6_calc.py (нагрузки в позах считаются по модели).

Пружина — в чаше голени Ø20 × 15 на оси колена (болт M5): наружный Ø ≤ 18,
внутренний Ø после закрутки ≥ 5.6, длина тела (n + 1)·d ≤ 14 мм.
Музыкальная проволока (EN 10270-1 DH): Sut = 2211 / d^0.145 МПа, E = 206 ГПа;
допускаемое напряжение при многократном нагружении — 0.6·Sut (с коэффициентом Ki).
"""
import math

E_MPA = 206000.0
KGCM = 98.0665            # Н·мм в 1 кг·см
CUP_OD, BOLT_ID, BODY_L = 18.0, 5.6, 14.0
KAPPA_LO = 65.0


def spring(d, od, n):
    """Жёсткость (Н·мм/рад), Dm, Ki, допускаемый момент (Н·мм)."""
    dm = od - d
    c = dm / d
    ki = (4 * c * c - c - 1) / (4 * c * (c - 1))
    sut = 2211.0 / d ** 0.145
    m_allow = 0.6 * sut * math.pi * d ** 3 / (32 * ki)
    k = E_MPA * d ** 4 / (64 * dm * n)
    return k, dm, ki, m_allow, sut


def torque(k, pre_deg, kappa):
    """Момент пружины в колене, кг·см (+ — разгибает)."""
    return k * math.radians(pre_deg + kappa - KAPPA_LO) / KGCM


def margins(loads, ratio, k, pre, have=11.0):
    """loads: [(поза, κ, момент нагрузки кг·см (+ сгибает), разброс ±)] → [(поза, κ, запас)]."""
    out = []
    for name, kap, t, spread in loads:
        ts = torque(k, pre, kap) if k else 0.0
        net = max(abs(t + spread - ts), abs(t - spread - ts))
        out.append((name, kap, have / max(net / ratio(kap), 1e-6)))
    return out


def optimize(loads, ratio, kappa_max, target=1.8):
    best = None
    for d in (1.0, 1.2, 1.4, 1.5, 1.6, 1.8, 2.0):
        for od in (12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0):
            for n in range(2, int(BODY_L / d)):
                if (n + 1) * d > BODY_L or od - d <= BOLT_ID + d:
                    continue
                k, dm, ki, m_allow, sut = spring(d, od, n)
                for pre in range(0, 181, 5):
                    theta_max = math.radians(pre + kappa_max - KAPPA_LO)
                    if k * theta_max > m_allow:
                        break
                    id_min = dm * n / (n + theta_max / (2 * math.pi)) - d
                    if id_min < BOLT_ID:
                        break
                    mm = min(m for _, _, m in margins(loads, ratio, k, pre))
                    key = (round(mm, 2), -pre, -d)
                    if best is None or key > best[0]:
                        best = (key, dict(d=d, od=od, dm=dm, n=n, k=k, pre=pre, ki=ki, sut=sut,
                                          m_allow=m_allow, theta_max_deg=math.degrees(theta_max),
                                          id_min=id_min, min_margin=mm))
    return best[1]


def describe(s, kappa_max):
    """Строки для документа: как купить или навить."""
    return [
        f"- Проволока пружинная (музыкальная, EN 10270-1 DH / ГОСТ 9389) **Ø{s['d']:.1f} мм**, "
        f"Sut ≈ {s['sut']:.0f} МПа.",
        f"- Наружный Ø **{s['od']:.0f} мм** (средний {s['dm']:.1f}, внутренний {s['od'] - 2 * s['d']:.1f}), "
        f"**{s['n']} рабочих витков**, длина тела {(s['n'] + 1) * s['d']:.1f} мм; ножки радиальные, "
        "15 мм: одна — в паз чаши голени, вторая — в упор на щеке бедра.",
        f"- Жёсткость **{s['k']:.0f} Н·мм/рад** ({s['k'] / KGCM:.2f} кг·см/рад, "
        f"{s['k'] * math.pi / 180:.2f} Н·мм/°).",
        f"- Натяг (предварительная закрутка) при κ = 65°: **{s['pre']}°** → момент "
        f"{torque(s['k'], s['pre'], 65):.2f} кг·см; при κ = {kappa_max:.0f}° закрутка "
        f"{s['theta_max_deg']:.0f}° → {torque(s['k'], s['pre'], kappa_max):.2f} кг·см "
        f"(допускаемо {s['m_allow'] / KGCM:.2f} кг·см при 0.6·Sut); внутренний Ø при этом {s['id_min']:.1f} мм.",
        "- Навивка: **2 левые + 2 правые** — пружины левых и правых ног зеркальны "
        "(сгиб колена в мире одинаковый, а ось чаши смотрит в разные стороны). Пружина при сгибании "
        "должна закручиваться (витки сжимаются по диаметру).",
        f"- Навить самому: оправка Ø{s['od'] - 2 * s['d'] - 1.5:.1f} (пружинение раскроет до ≈ Ø"
        f"{s['od'] - 2 * s['d']:.0f} внутр.), {s['n']} витков вплотную, отпуск 250 °C 30 мин. "
        "Чаша голени: Ø22 снаружи, Ø18.6 внутри, глубина 15.",
    ]
