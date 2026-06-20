ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS is_depot BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE vehicles SET is_depot = TRUE WHERE vehicle_code IN ('Tesla_01', 'Hyundai_02');
