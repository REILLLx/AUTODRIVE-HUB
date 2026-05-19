import os
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
BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP', 'localhost:9092')
DELAY_SECONDS = 0.5
PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sender.pause')

if KAFKA_AVAILABLE:
    producer = Producer({'bootstrap.servers': BOOTSTRAP_SERVERS})

def delivery_report(err, msg):
    if err is not None:
        print(f"❌ Помилка доставки: {err}")

def run_sender():
    df = pd.read_csv(FILE_NAME)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(by='timestamp')

    print(f"🚀 Починаємо відправку даних для {df['vehicle_id'].nunique()} автомобілів...")

    for _, row in df.iterrows():
        while os.path.exists(PAUSE_FILE):
            time.sleep(0.5)

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
            }
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
