import os
import random
import pandas as pd
import json
import time
try:
    from confluent_kafka import Producer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

FILE_NAME = 'synthetic_ev_data_send.csv'
TOPIC_NAME = 'ev_telemetry'
BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP', 'localhost:29092')
DELAY_SECONDS = 0.5
PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sender.pause')


DEPOT_VEHICLES = {'Tesla_01', 'Hyundai_02'}

# Стан поточної сесії збою для кожного авто: {vehicle_id: {'code': str, 'ends_at': float}}
_sensor_sessions: dict = {}

def generate_sensor_data(v_id: str) -> dict:
    if v_id in DEPOT_VEHICLES:
        return {'camera_blinded': False, 'sensor_array_status': 'OK', 'ad_mode': 'AUTONOMOUS'}

    now = time.time()
    session = _sensor_sessions.get(v_id)

    if session and session['ends_at'] > now:
        # Продовжуємо активну сесію збою — код стабільний весь час
        if session['code'] == 'SENSOR_ARR_DEGRADED':
            return {'camera_blinded': False, 'sensor_array_status': 'DEGRADED', 'ad_mode': 'MANUAL_OVERRIDE'}
        else:
            return {'camera_blinded': True, 'sensor_array_status': 'OK', 'ad_mode': 'MANUAL_OVERRIDE'}

    # Малий шанс почати нову сесію збою (~раз на 2-3 хвилини на авто)
    if random.random() < 0.004:
        code = random.choices(['SENSOR_ARR_DEGRADED', 'SENSOR_CAM_BLIND'], weights=[60, 40])[0]
        _sensor_sessions[v_id] = {'code': code, 'ends_at': now + random.uniform(90, 180)}
        if code == 'SENSOR_ARR_DEGRADED':
            return {'camera_blinded': False, 'sensor_array_status': 'DEGRADED', 'ad_mode': 'MANUAL_OVERRIDE'}
        else:
            return {'camera_blinded': True, 'sensor_array_status': 'OK', 'ad_mode': 'MANUAL_OVERRIDE'}

    # Нормальна робота
    mode = random.choices(['AUTONOMOUS', 'MANUAL_OVERRIDE'], weights=[95, 5])[0]
    return {'camera_blinded': False, 'sensor_array_status': 'OK', 'ad_mode': mode}


if KAFKA_AVAILABLE:
    producer = Producer({'bootstrap.servers': BOOTSTRAP_SERVERS})

def delivery_report(err, msg):
    if err is not None:
        print(f"❌ Помилка доставки: {err}")

DEMO_TRIGGER_MSG  = 80   # ~40 секунд від старту
DEMO_VEHICLE      = 'VW_01'
DEMO_FAULT_CODE   = 'SENSOR_ARR_DEGRADED'
DEMO_DURATION_SEC = 120  # 2 хвилини

def run_sender():
    df = pd.read_csv(FILE_NAME)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(by='timestamp')

    print(f"🚀 Починаємо відправку даних для {df['vehicle_id'].nunique()} автомобілів...")

    msg_count = 0
    for _, row in df.iterrows():
        while os.path.exists(PAUSE_FILE):
            time.sleep(0.5)

        msg_count += 1
        if msg_count == DEMO_TRIGGER_MSG and DEMO_VEHICLE not in _sensor_sessions:
            _sensor_sessions[DEMO_VEHICLE] = {
                'code': DEMO_FAULT_CODE,
                'ends_at': time.time() + DEMO_DURATION_SEC,
            }
            print(f"🎬 ДЕМО: {DEMO_VEHICLE} → {DEMO_FAULT_CODE} на {DEMO_DURATION_SEC}с")

        telemetry_packet = {
            "vehicle_metadata": {
                "vehicle_id": row['vehicle_id'],
                "brand": row['brand'],
                "model": row['model'],
                "timestamp": row['timestamp'].strftime('%Y-%m-%dT%H:%M:%SZ')
            },
            "location": {
                "lat": float(row['gps_lat']),
                "lon": float(row['gps_lon']),
                "speed_kph": float(row['vehicle_speed_kph'])
            },
            "energy_system": {
                "soc_pct": float(row['soc_pct']),
                "soh_pct": float(row['soh_pct']),
                "battery_temp_c": float(row['battery_temp_c'])
            },
            "mechanical_system": {
                "brake_pad_wear_mm": float(row['brake_pad_wear_mm']),
                "abs_fault_indicator": int(row['abs_fault_indicator'])
            },
            "diagnostics": {
                "active_error_code": str(row['active_error_code']) if pd.notna(row['active_error_code']) and row['active_error_code'] != "" else "None"
            },
            "sensors": {
                "battery_current_a": float(row['battery_current_a']),
                "acceleration_ms2":  float(row['acceleration_ms2']),
                "ambient_temp_c":    float(row['ambient_temp_c']),
                "power_kw":          float(row['power_kw']),
            },
            "sensor_status": generate_sensor_data(row['vehicle_id'])
        }

        message_payload = json.dumps(telemetry_packet)

        if KAFKA_AVAILABLE:
            producer.produce(TOPIC_NAME, value=message_payload, callback=delivery_report)
            producer.poll(0)
        else:
            print(f"DEBUG: {message_payload}")

        time.sleep(DELAY_SECONDS)

    if KAFKA_AVAILABLE:
        producer.flush()

if __name__ == "__main__":
    run_sender()
