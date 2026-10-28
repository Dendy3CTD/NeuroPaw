"""
NeuroPaw — v6_params_bom.py
Приводит params.json к окончательному списку покупок (28.10.2026):
электроника, I2C, CAN, подшипники. Всё, чего нет в смете, удаляется; питание остаётся,
но помечено purchased=False («не закуплено»).
Запуск: python3 scripts/v6_params_bom.py
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE, "params.json")
P = json.load(open(PATH))


def part(board, size, mass_g, section, row, peak=0.0, avg=0.0, measure=True, purchased=True, **kw):
    """row — № строки сметы (None — нет в смете); measure — размер замерить с реальной детали."""
    return {"board": board, "size": size, "mass_g": mass_g, "section": section, "estimate_row": row,
            "i5_peak_a": peak, "i5_avg_a": avg, "measure": measure, "purchased": purchased, **kw}


NOT_BOUGHT = dict(purchased=False, measure=False)
P["electronics"] = {
    "ESP32_Body": part("ESP32 DevKit CH340 (ESP32-WROOM-32), 38 выводов", [55, 28, 13], 9.5, "rear", 5,
                       0.25, 0.08, note="30-выводная 51×28 тоже встаёт в то же место"),
    "ESP32_Senses": part("ESP32-S3-DevKitC-1 N16R8", [69, 26, 13], 10, "head", 6, 0.3, 0.12,
                         note="длина 63–69 по продавцу, в модели 69"),
    "ESP32_Brain": part("ESP32-S3-CAM N16R8 + камера OV2640", [64, 27, 7], 11, "head", 7, 0.45, 0.3,
                        note="типовая плата с двумя USB-C (USB/OTG и COM); гребёнки не паять"),
    "ESP32_Comms": part("ESP32-C3 SuperMini", [22.5, 18, 4.8], 2, "front", 8, 0.35, 0.1),
    "CAN_transceiver": part("SN65HVD230, набор 4 шт.", [20, 15, 3.4], 2, "all", 9, 0.01, 0.01,
                            note="масса на модуль; 120 Ом снять на «Мозге» и «Связи»"),
    "PCA9685_Body": part("PCA9685 16 кан., 0x40 (+ тестер серв)", [62.5, 25.4, 10], 9, "rear", 10,
                         0.01, 0.01, measure=False),
    "IMU_front": part("GY-521 MPU-6050, 0x69 (AD0 = 1)", [21.2, 16.4, 3.2], 3, "front", 11, 0.005, 0.005),
    "IMU_rear": part("MPU-6050 (имеется; принят GY-521), 0x68", [21.2, 16.4, 3.2], 3, "rear", 12,
                     0.005, 0.005, note="уточнить модель имеющегося модуля"),
    "Sonar_HCSR04": part("HC-SR04 (имеется)", [45, 20, 15], 9, "front", 13, 0.015, 0.015,
                         note="Echo 5 В → делитель 1 кОм / 2 кОм → 3.3 В"),
    "INA226_jaw": part("INA226 (шунт 0.1 Ом, до 0.82 А), 0x40 на шине «Органов чувств»", [20, 25, 3], 2,
                       "head", 14, 0.001, 0.001),
    "Mics_INMP441": part("INMP441, набор 2 шт.", [14, 14, 3], 1.5, "head", 15, 0.002, 0.002,
                         note="масса на модуль"),
    "Eyes_GC9A01": part("GC9A01 1.28\" 240×240 SPI", [38.6, 38.6, 4.5], 6, "head", 16, 0.06, 0.04,
                        note="на экран; подсветка ≤ 50 %"),
    "Amp_MAX98357A": part("MAX98357A I2S 3 Вт", [18, 19, 3], 2, "head", 17, 0.7, 0.05,
                          note="клеммник не впаивать — провода динамика пайкой"),
    "Speaker": part("динамик 35×25 мм 4 Ом 3 Вт (1 из набора 2 шт.)", [35, 25, 5], 7, "head", 18),
    "USB_flash": part("флешка 50 ГБ USB-A (имеется)", [45, 16, 8], 6, "head", 19, 0.1, 0.03,
                      note="длина принята 45 мм с разъёмом"),
    "OTG_adapter": part("OTG-переходник USB-C → USB-A (жёсткий)", [24, 16, 8], 4, "spare", 20,
                        note="в голове не помещается по длине — для отладки на столе"),
    "OTG_cable": part("OTG-кабель USB-C 90° → USB-A гнездо, 10 см", [22, 15, 8], 8, "head", None,
                      measure=True, purchased=False, note="нет в смете — нужен вместо жёсткого"),
    # питание — по power.md, не закуплено (в смете «Не учтено (позже)»)
    "Battery_2S2P": part("Molicel P28A × 4 (2S2P 5600 мА·ч)", [76, 67, 20], 190, "rear", None, **NOT_BOUGHT),
    "BMS": part("BMS 2S 40 А", [45, 20, 4], 15, "rear", None, **NOT_BOUGHT),
    "UBEC_F": part("UBEC 6 В 20 А «П»: передние ноги, шея, челюсть, уши", [46, 27, 13], 30, "front",
                   None, **NOT_BOUGHT),
    "UBEC_R": part("UBEC 6 В 20 А «З»: задние ноги, позвоночник, хвост", [46, 27, 13], 30, "rear",
                   None, **NOT_BOUGHT),
    "DCDC_5V_5A": part("DC-DC 7.4 → 5 В 5 А (Mini560 Pro)", [21, 16, 5], 4, "front", None, **NOT_BOUGHT),
    "Fuses": part("40 А главный, 25 А × 2 (UBEC), 5 А (логика), держатели mini-blade", [25, 10, 15], 3,
                  "all", None, **NOT_BOUGHT),
    "MOSFET_switches": part("P-MOSFET ключи веток (мягкий старт)", [25, 20, 5], 3, "all", None, **NOT_BOUGHT),
    "Capacitors": part("2200 мкФ 10 В Low-ESR × 3", [12.5, 12.5, 20], 4, "all", None, **NOT_BOUGHT),
    "XT60_loopkey": part("XT60 гнездо + XT60 loop-key", [16, 8, 16], 5, "rear", None, **NOT_BOUGHT),
    "Dock_contacts": part("контакты док-станции (резерв места)", [36, 36, 5], 0, "rear", None, **NOT_BOUGHT),
}

P["i2c"] = {
    "ESP32_Body": {"pins": "SDA GPIO21 / SCL GPIO22", "freq_hz": 400000,
                   "pullup": "на модулях GY-521 4.7 кОм × 2 + PCA9685 10 кОм ≈ 2 кОм — внешних не нужно",
                   "devices": {"0x40": "PCA9685", "0x68": "MPU-6050 задний (AD0 = 0)",
                               "0x69": "MPU-6050 передний (AD0 = 1), витая пара через позвоночник ≤ 20 см",
                               "0x70": "PCA9685 All-Call (не занимать)"}},
    "ESP32_Senses": {"pins": "SDA GPIO8 / SCL GPIO9", "freq_hz": 400000, "pullup": "на модуле INA226",
                     "devices": {"0x40": "INA226 — ток сервы челюсти (A0 = A1 = GND)"}},
}

P["can"]["boards"] = {"ESP32_Senses": "ESP32-S3", "ESP32_Brain": "ESP32-S3", "ESP32_Comms": "ESP32-C3",
                      "ESP32_Body": "ESP32 (WROOM-32)"}
P["can"]["transceiver"] = "SN65HVD230 (3.3 В) × 4, у каждой платы; TWAI есть во всех трёх семействах"

P["bearings"] = {
    "625ZZ": {"d": 5, "D": 16, "B": 5, "mass_g": 4.6, "seat_d": 16.2, "qty_model": 22, "qty_need": 24,
              "use": "отведение 4 (мосты груди и кормы), бедро 4, колено 8, позвоночник 2 + 2 (пары), "
                     "наклон шеи 2 (пара); оси — болты M5 с гайкой и фиксатором резьбы"},
    "MR683ZZ": {"d": 3, "D": 7, "B": 3, "mass_g": 0.5, "seat_d": 7.2, "qty_model": 2, "qty_need": 2,
                "use": "ось челюсти, ответная сторона (пара в правой щеке), ось — винт M3"},
    "51100": {"d": 10, "D": 24, "B": 9, "mass_g": 16, "qty_model": 1, "qty_need": 1,
              "use": "поворот шеи: держит вес головы, MG90S только вращает"},
}

P["power"]["purchased"] = False
P["power"]["battery_sense"] = "делитель 100 кОм / 33 кОм → GPIO36 (ADC1) «Тела»; INA226 батареи убран"
P["power"]["dock"] = "место под два контакта док-станции в дне задней секции (x −40…−19, y −23…−13)"
for s in P["servo_table"]:
    if s["no"] == 18:
        s["power"] = "UBEC_F через INA226"

for s_ in P["servo_table"]:
    if s_["no"] in (3, 6, 9, 12):
        s_["range"] = [-128, -65]          # упор 128.5°, мёртвая точка тяги 130.04°
P["knee_linkage"].update(toggle_deg=130.04, stop_deg=128.5, work_max_deg=128.0)
json.dump(P, open(PATH, "w"), ensure_ascii=False, indent=2)
print("[params] электроника:", len(P["electronics"]), "позиций; подшипники:", list(P["bearings"]))
