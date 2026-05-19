import pandas as pd
import numpy as np
import math
import random
from datetime import datetime, timedelta

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

ROWS_PER_CAR = 4000
STEP_SECONDS = 30
NOMINAL_VOLTAGE = 400

DEPOT = (50.4501, 30.5234)

DEPOT_CONFIG = {
    "Tesla_01":   {"lat": 50.4501, "lon": 30.5234, "radius_m": 50},
    "Hyundai_01": {"lat": 50.4501, "lon": 30.5234, "radius_m": 50},
    "Tesla_02":   {"lat": 50.4501, "lon": 30.5234, "radius_m": 50},
    "VW_01":      {"lat": 50.4501, "lon": 30.5234, "radius_m": 50},
    "Hyundai_02": {"lat": 50.4501, "lon": 30.5234, "radius_m": 50},
}

DIRECTION = {
    "Tesla_01":   math.radians(270),
    "Hyundai_01": math.radians(240),
    "Tesla_02":   math.radians(225),
    "VW_01":      math.radians(320),
    "Hyundai_02": math.radians(240),
}

SCENARIOS = {
    "Tesla_01": [
        ("low_charge",     0,    800),
        ("parking",        800,  1600),
        ("partial_charge", 1600, 2200),
        ("parking",        2200, 4000),
    ],

    "Hyundai_02": [
        ("charging", 0,    500),
        ("parking",  500, 4000),
    ],

    "Hyundai_01": [
        ("traffic", 0,    800),
        ("normal",  800,  1500),
        ("parking", 1500, 4000),
    ],

    "Tesla_02": [
        ("normal",         0,    700),
        ("brake_wear",     700,  1800),
        ("fast_discharge", 1800, 2500),
        ("congestion",     2500, 3200),
        ("normal",         3200, 4000),
    ],

    "VW_01": [
        ("normal",      0,    600),
        ("normal",      600,  1400),
        ("overheating", 1400, 4000),
    ],
}

INITIAL_SOC = {
    "Tesla_01":   90.0,
    "Hyundai_01": 20.0,
    "Tesla_02":   90.0,
    "VW_01":      90.0,
    "Hyundai_02": 30.0,
}

CARS = [
    {"id": "Tesla_01",   "brand": "Tesla",   "model": "Model 3"},
    {"id": "Hyundai_01", "brand": "Hyundai", "model": "Ioniq 6"},
    {"id": "Tesla_02",   "brand": "Tesla",   "model": "Model 3"},
    {"id": "VW_01",      "brand": "VW",      "model": "ID.4"},
    {"id": "Hyundai_02", "brand": "Hyundai", "model": "Ioniq 6"},
]


def get_ambient_temp(timestamp):
    hour = timestamp.hour
    day = timestamp.day
    base_temp = 12.0
    daily_variation = 6.0 * math.sin((hour - 6) * math.pi / 12)
    weather_noise = math.sin(day * 0.5) * 3.0
    random_noise = np.random.normal(0, 1.5)
    temp = base_temp + daily_variation + weather_noise + random_noise
    return round(max(-5, min(25, temp)), 1)


def get_scenario(step, scenarios):
    for (stype, start, end) in scenarios:
        if start <= step < end:
            return stype
    return "normal"


def move_gps(lat, lon, direction, speed_kph, step_sec=30):
    dist_m = speed_kph * 1000 / 3600 * step_sec
    angle = direction + math.radians(np.random.uniform(-15, 15))
    dlat = (dist_m * math.cos(angle)) / 111_000
    dlon = (dist_m * math.sin(angle)) / (111_000 * math.cos(math.radians(lat)))
    dlat += np.random.normal(0, 0.000018)
    dlon += np.random.normal(0, 0.000018)
    return round(lat + dlat, 6), round(lon + dlon, 6)


data = []
start_time = datetime(2026, 4, 6, 10, 0, 0)

for car in CARS:
    vid   = car["id"]
    brand = car["brand"]
    model = car["model"]

    soc        = INITIAL_SOC.get(vid, 90.0)
    temp       = 25.0
    soh        = 98.0
    brake_wear = 8.0
    direction  = DIRECTION[vid]

    lat, lon   = DEPOT
    depot_lat, depot_lon = DEPOT

    car_scen   = SCENARIOS[vid]
    prev_speed = 0.0

    for i in range(ROWS_PER_CAR):
        timestamp = start_time + timedelta(seconds=i * STEP_SECONDS)
        stype     = get_scenario(i, car_scen)
        error_code = None
        abs_fault  = 0

        ambient_temp = get_ambient_temp(timestamp)

        if stype in ("parking",):
            speed = 0.0
            lat += np.random.normal(0, 0.000015)
            lon += np.random.normal(0, 0.000015)

        elif stype in ("charging", "low_charge", "partial_charge"):
            speed = 0.0
            lat += np.random.normal(0, 0.000015)
            lon += np.random.normal(0, 0.000015)

        elif stype == "fast_discharge":
            speed = round(np.random.uniform(45, 55), 1)
            lat, lon = move_gps(lat, lon, direction, speed)

        elif stype == "traffic":
            if i % 8 < 2:
                speed = 0.0
                lat += np.random.normal(0, 0.000015)
                lon += np.random.normal(0, 0.000015)
            else:
                speed = round(np.random.uniform(20, 40), 1)
                lat, lon = move_gps(lat, lon, direction, speed)

        elif stype == "congestion":
            if random.random() < 0.25:
                speed = 0.0
                lat += np.random.normal(0, 0.000015)
                lon += np.random.normal(0, 0.000015)
            else:
                speed = round(np.random.uniform(3, 12), 1)
                lat, lon = move_gps(lat, lon, direction, speed)

        else:
            speed = round(np.random.uniform(20, 30), 1)
            lat, lon = move_gps(lat, lon, direction, speed)

        speed_ms = speed * 0.27778
        prev_speed_ms = prev_speed * 0.27778
        acceleration = (speed_ms - prev_speed_ms) / STEP_SECONDS
        acceleration = round(acceleration, 2)

        if stype == "normal":
            soc_delta = -(0.008 + speed * 0.00012 + np.random.normal(0, 0.002))
            temp += np.random.normal(0, 0.05)

        elif stype == "fast_discharge":
            soc_delta = -(0.02 + speed * 0.00015 + np.random.normal(0, 0.003))
            temp = min(48, temp + np.random.uniform(0, 0.1))

        elif stype == "charging":
            soc_delta = +0.06 + np.random.normal(0, 0.005) if soc < 90.0 else 0.0
            temp = min(33, temp + abs(np.random.normal(0, 0.02)))

        elif stype == "low_charge":
            if soc < 20:
                soc_delta = +0.03 + np.random.normal(0, 0.003)
            elif soc < 80:
                soc_delta = +0.06 + np.random.normal(0, 0.005)
            elif soc < 90:
                soc_delta = +0.02 + np.random.normal(0, 0.002)
            else:
                soc_delta = 0.0
            temp = min(33, temp + abs(np.random.normal(0, 0.02)))

        elif stype == "partial_charge":
            soc_delta = +0.05 + np.random.normal(0, 0.004) if soc < 75.0 else 0.0
            temp = min(35, temp + abs(np.random.normal(0, 0.05)))

        elif stype == "parking":
            soc_delta = -0.001
            temp += (ambient_temp - temp) * 0.02

        elif stype == "battery_issue":
            soc_delta  = -0.35 + np.random.normal(0, 0.01)
            error_code = "P0AA6"
            temp += np.random.normal(0, 0.05)

        elif stype == "overheating":
            soc_delta = -(0.01 + np.random.normal(0, 0.002))
            temp      = min(80.0, temp + 0.05)
            if temp > 60:
                error_code = "P1B74"

        elif stype == "brake_wear":
            soc_delta   = -(0.008 + speed * 0.00012)
            brake_wear -= 0.008
            brake_wear  = max(0, brake_wear)
            if brake_wear < 2.5:
                error_code = "C1235"
                abs_fault  = 1
            temp += np.random.normal(0, 0.05)

        elif stype == "traffic":
            if speed == 0:
                soc_delta = -0.001
            else:
                soc_delta = -(0.009 + speed * 0.00013 + np.random.normal(0, 0.002))
            temp += np.random.normal(0, 0.05)

        elif stype == "congestion":
            if speed == 0:
                soc_delta = -0.001
            else:
                soc_delta = -(0.004 + speed * 0.00008 + np.random.normal(0, 0.001))
            temp += np.random.normal(0, 0.04)

        else:
            soc_delta = -0.008
            temp += np.random.normal(0, 0.05)

        soc  = round(max(0.0, min(100.0, soc + soc_delta)), 2)
        temp = max(15.0, min(82.0, temp))

        if error_code is None and random.random() < 0.001:
            internal_codes = {
                "Tesla":   ["BMS_a066", "DI_a138", "APP_w207"],
                "Hyundai": ["DI_a035", "BMS_a042"],
                "VW":      ["APP_w009", "DI_a052"],
            }
            pool = internal_codes.get(brand, [])
            if pool:
                error_code = random.choice(pool)

        if stype in ("charging", "low_charge", "partial_charge"):
            if soc < 20:
                current = -120 + np.random.normal(0, 5)
            elif soc < 80:
                current = -80 + np.random.normal(0, 5)
            else:
                current = -30 + np.random.normal(0, 3)
        elif stype == "parking":
            current = 3 + np.random.normal(0, 0.5)
        elif speed == 0:
            current = 5 + np.random.normal(0, 1)
        else:
            base_current = 25
            speed_factor = speed * 0.6
            accel_factor = max(0, acceleration) * 5
            if acceleration < -0.5:
                regen = abs(acceleration) * 10
                current = max(-40, base_current + speed_factor - regen)
            else:
                current = base_current + speed_factor + accel_factor
            current += np.random.normal(0, 3)

        if temp < 10:
            current *= 1.2
        elif temp > 35:
            current *= 1.1

        current = round(current, 1)

        power_kw = round(current * NOMINAL_VOLTAGE / 1000, 2)

        data.append([
            vid, brand, model, timestamp,
            round(lat, 6), round(lon, 6), speed,
            soc, temp, round(soh, 1),
            round(brake_wear, 3), abs_fault, error_code,
            current, acceleration, ambient_temp, power_kw,
        ])

        prev_speed = speed

columns = [
    "vehicle_id", "brand", "model", "timestamp",
    "gps_lat", "gps_lon", "vehicle_speed_kph",
    "soc_pct", "battery_temp_c", "soh_pct",
    "brake_pad_wear_mm", "abs_fault_indicator", "active_error_code",
    "battery_current_a", "acceleration_ms2", "ambient_temp_c", "power_kw",
]
df = pd.DataFrame(data, columns=columns)

filename = "synthetic_ev_data_train.csv"
df.to_csv(filename, index=False)

print(f"✅ Датасет: {len(df)} рядків | {df['vehicle_id'].nunique()} авто → {filename}")
print()
for vid, g in df.groupby("vehicle_id"):
    g       = g.sort_values("timestamp")
    moving  = g[g["vehicle_speed_kph"] > 0]
    standing= g[g["vehicle_speed_kph"] == 0]
    errors  = g["active_error_code"].dropna()
    soc_up  = (g["soc_pct"].diff() > 0).sum()

    print(f"  {vid}:")
    print(f"    SOC: {g['soc_pct'].max():.1f}% → {g['soc_pct'].min():.1f}%  "
          f"(зростання: {soc_up} кроків)")
    print(f"    Speed: {moving['vehicle_speed_kph'].mean():.1f} км/год сер. | "
          f"В русі: {len(moving)} | Стоїть: {len(standing)}")
    print(f"    Temp: {g['battery_temp_c'].min():.1f}-{g['battery_temp_c'].max():.1f}°C | "
          f"Ambient: {g['ambient_temp_c'].min():.1f}-{g['ambient_temp_c'].max():.1f}°C")
    print(f"    Current: {g['battery_current_a'].min():.1f}A → {g['battery_current_a'].max():.1f}A")
    print(f"    Power: {g['power_kw'].min():.1f} → {g['power_kw'].max():.1f} kW")
    print(f"    Помилки: {len(errors)} записів → {list(errors.unique())}")
    print()
