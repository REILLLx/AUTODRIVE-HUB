import json
import math
import psycopg2
import numpy as np
import joblib
from confluent_kafka import Consumer
from tensorflow.keras.models import load_model
import re

import os

KAFKA_CONF = {
    'bootstrap.servers': os.environ.get('KAFKA_BOOTSTRAP', 'localhost:9092'),
    'group.id': 'ev_group',
    'auto.offset.reset': 'earliest'
}
DB_CONF = os.environ.get('DB_CONF', 'host=127.0.0.1 dbname=ev_telemetry_db user=admin password=root port=5432')

DEPOT_CONFIG = {
    vid: {"lat": 50.4501, "lon": 30.5234, "radius_m": 100}
    for vid in ["Tesla_01", "Hyundai_01", "Tesla_02", "VW_01", "Hyundai_02"]
}

print("🧠 Завантаження модулів: LSTM + Gemini...")
model  = load_model('ev_model.keras')
scaler = joblib.load('scaler.gz')

history_buffer = {}
geofence_state = {}


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_verdict(output: str) -> tuple[float | None, str]:
    score = None
    score_match = re.search(r'SCORE:\s*([0-9.]+)', output)
    if score_match:
        try:
            score = float(score_match.group(1))
            score = max(0.0, min(1.0, score))
        except Exception:
            score = None
    verdict_text = re.sub(r'SCORE:\s*[0-9.]+\n?', '', output).strip()
    return score, verdict_text


def check_geofence(v_id_code: str, lat: float, lon: float, conn):
    cfg = DEPOT_CONFIG.get(v_id_code)
    if not cfg:
        return

    dist   = haversine_m(lat, lon, cfg["lat"], cfg["lon"])
    inside = dist <= cfg["radius_m"]
    prev   = geofence_state.get(v_id_code)

    if prev is None:
        geofence_state[v_id_code] = inside
        event_type = 'ENTERED' if inside else 'EXITED'
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO geofence_events
                    (vehicle_id, event_type, lat, lon, distance_m)
                VALUES
                    ((SELECT id FROM vehicles WHERE vehicle_code = %s), %s, %s, %s, %s)
            """, (v_id_code, event_type, lat, lon, round(dist, 1)))
        icon = "🟢" if inside else "🔴"
        print(f"📍 ІНІЦІАЛІЗАЦІЯ: {icon} {v_id_code} -> {event_type} ({dist:.0f}м)")
        return

    if prev == inside:
        return

    geofence_state[v_id_code] = inside
    event_type = 'ENTERED' if inside else 'EXITED'
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO geofence_events
                (vehicle_id, event_type, lat, lon, distance_m)
            VALUES
                ((SELECT id FROM vehicles WHERE vehicle_code = %s), %s, %s, %s, %s)
        """, (v_id_code, event_type, lat, lon, round(dist, 1)))
    icon = "🟢" if inside else "🔴"
    print(f"📍 ГЕОФЕНС: {icon} {v_id_code} -> {event_type} ({dist:.0f}м)")


def check_return_recommendation(v_id_code: str, current_soc: float,
                                pred_real: float, lat: float, lon: float, conn):
    cfg = DEPOT_CONFIG.get(v_id_code)
    if not cfg:
        return

    dist_m = haversine_m(lat, lon, cfg["lat"], cfg["lon"])

    reason = None
    if current_soc < 15:
        reason = f"Критично низький заряд: {current_soc:.1f}%"
    elif pred_real < 20:
        reason = f"Прогноз LSTM: заряд впаде до {pred_real:.1f}%"
    elif (current_soc - pred_real) > 5:
        reason = f"Швидкий розряд: -{(current_soc - pred_real):.1f}% за годину"

    if reason is None:
        return

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id FROM depot_recommendations
            WHERE vehicle_id = (SELECT id FROM vehicles WHERE vehicle_code = %s)
              AND status = 'active'
        """, (v_id_code,))
        if cur.fetchone():
            return

        cur.execute("""
            INSERT INTO depot_recommendations
                (vehicle_id, current_soc, predicted_soc, distance_to_depot_m, reason)
            VALUES
                ((SELECT id FROM vehicles WHERE vehicle_code = %s), %s, %s, %s, %s)
        """, (v_id_code, current_soc, round(float(pred_real), 2), round(dist_m), reason))

    print(f"🔔 РЕКОМЕНДАЦІЯ: {v_id_code} -> повернутись в депо | {reason} | {dist_m:.0f}м")


def run_receiver():
    consumer = Consumer(KAFKA_CONF)
    consumer.subscribe(['ev_telemetry'])
    print("📥 Система активована.")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            data        = json.loads(msg.value().decode('utf-8'))
            v_id_code   = data['vehicle_metadata']['vehicle_id']
            error_code  = data['diagnostics'].get('active_error_code')
            lat         = data['location']['lat']
            lon         = data['location']['lon']
            speed       = data['location']['speed_kph']
            current_soc = data['energy_system']['soc_pct']

            current_features = [
                current_soc,
                speed,
                data['energy_system']['battery_temp_c'],
            ]
            if v_id_code not in history_buffer:
                history_buffer[v_id_code] = []
            history_buffer[v_id_code].append(current_features)
            if len(history_buffer[v_id_code]) > 40:
                history_buffer[v_id_code].pop(0)

            pred_real = None
            if len(history_buffer[v_id_code]) >= 40:
                input_seq    = np.array(history_buffer[v_id_code][-40:])
                input_scaled = scaler.transform(input_seq)
                input_final  = np.reshape(input_scaled, (1, 40, 3))
                pred_scaled  = model.predict(input_final, verbose=0)
                dummy        = np.zeros((1, 3))
                dummy[0, 0]  = pred_scaled[0, 0]
                pred_real    = scaler.inverse_transform(dummy)[0, 0]
                pred_real    = max(0.0, min(100.0, pred_real))

                if v_id_code not in ('Tesla_01', 'Hyundai_02'):
                    print(f"🚗 {v_id_code} | SOC: {current_soc}% | ПРОГНОЗ: {pred_real:.2f}%")
                    if pred_real < 15.0:
                        print(f"🚨 ALERT: Критично низький прогноз заряду для {v_id_code}!")
                else:
                    pred_real = None

            with psycopg2.connect(DB_CONF) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO vehicle_telemetry
                            (vehicle_id, timestamp, lat, lon, speed_kph,
                             soc_pct, soh_pct, battery_temp_c,
                             brake_pad_wear_mm, abs_fault_indicator, active_error_code,
                             battery_current_a, acceleration_ms2, ambient_temp_c, power_kw)
                        VALUES
                            ((SELECT id FROM vehicles WHERE vehicle_code = %s),
                             %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        v_id_code,
                        data['vehicle_metadata']['timestamp'],
                        lat, lon, speed,
                        current_soc,
                        data['energy_system']['soh_pct'],
                        data['energy_system']['battery_temp_c'],
                        data['mechanical_system']['brake_pad_wear_mm'],
                        data['mechanical_system']['abs_fault_indicator'],
                        error_code,
                        data['sensors']['battery_current_a'],
                        data['sensors']['acceleration_ms2'],
                        data['sensors']['ambient_temp_c'],
                        data['sensors']['power_kw'],
                    ))

                    if pred_real is not None:
                        cur.execute("""
                            INSERT INTO lstm_predictions
                                (vehicle_id, current_soc, predicted_soc)
                            VALUES
                                ((SELECT id FROM vehicles WHERE vehicle_code = %s), %s, %s)
                        """, (v_id_code, current_soc, round(float(pred_real), 2)))

                check_geofence(v_id_code, lat, lon, conn)

                if pred_real is not None:
                    check_return_recommendation(
                        v_id_code, current_soc, pred_real, lat, lon, conn
                    )

    except KeyboardInterrupt:
        print("⛔ Зупинка.")
    except Exception as e:
        print(f"⚠️  Помилка ресівера: {e}")
    finally:
        consumer.close()


if __name__ == "__main__":
    run_receiver()
