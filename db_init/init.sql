CREATE TABLE IF NOT EXISTS vehicles (
    id           SERIAL PRIMARY KEY,
    vehicle_code VARCHAR(50) UNIQUE NOT NULL,
    brand        VARCHAR(50),
    model        VARCHAR(50),
    plate_number VARCHAR(20),
    is_depot     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS vehicle_telemetry (
    id                 SERIAL PRIMARY KEY,
    vehicle_id         INTEGER REFERENCES vehicles(id) ON DELETE CASCADE,
    timestamp          TIMESTAMP,
    lat                FLOAT,
    lon                FLOAT,
    speed_kph          FLOAT,
    soc_pct            FLOAT,
    soh_pct            FLOAT,
    battery_temp_c     FLOAT,
    brake_pad_wear_mm  FLOAT,
    abs_fault_indicator INTEGER,
    active_error_code  VARCHAR(50),
    battery_current_a  FLOAT,
    acceleration_ms2   FLOAT,
    ambient_temp_c     FLOAT,
    power_kw           FLOAT,
    ad_mode            VARCHAR(20) DEFAULT 'AUTONOMOUS',
    camera_blinded     BOOLEAN DEFAULT FALSE,
    sensor_array_status VARCHAR(20) DEFAULT 'OK',
    sensor_fault_code  VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS lstm_predictions (
    id            SERIAL PRIMARY KEY,
    vehicle_id    INTEGER REFERENCES vehicles(id) ON DELETE CASCADE,
    predicted_at  TIMESTAMP DEFAULT NOW(),
    current_soc   FLOAT,
    predicted_soc FLOAT
);

CREATE TABLE IF NOT EXISTS geofence_events (
    id          SERIAL PRIMARY KEY,
    vehicle_id  INTEGER REFERENCES vehicles(id) ON DELETE CASCADE,
    event_type  VARCHAR(20),
    lat         FLOAT,
    lon         FLOAT,
    distance_m  FLOAT,
    timestamp   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS depot_recommendations (
    id                  SERIAL PRIMARY KEY,
    vehicle_id          INTEGER REFERENCES vehicles(id) ON DELETE CASCADE,
    current_soc         FLOAT,
    predicted_soc       FLOAT,
    distance_to_depot_m FLOAT,
    reason              TEXT,
    status              VARCHAR(20) DEFAULT 'active',
    created_at          TIMESTAMP DEFAULT NOW()
);

INSERT INTO vehicles (vehicle_code, brand, model, plate_number, is_depot) VALUES
    ('Tesla_01',   'Tesla',   'Model 3', 'AA 1234 BC', TRUE),
    ('Hyundai_01', 'Hyundai', 'Ioniq 6', 'KA 5678 MH', FALSE),
    ('Tesla_02',   'Tesla',   'Model 3', 'AA 9012 DE', FALSE),
    ('VW_01',      'VW',      'ID.4',    'KA 3456 PO', FALSE),
    ('Hyundai_02', 'Hyundai', 'Ioniq 6', 'AA 7890 XY', TRUE)
ON CONFLICT (vehicle_code) DO NOTHING;
