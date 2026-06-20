ALTER TABLE vehicle_telemetry
    ADD COLUMN IF NOT EXISTS sensor_array_status VARCHAR(20) DEFAULT 'OK',
    ADD COLUMN IF NOT EXISTS sensor_fault_code   VARCHAR(50);
