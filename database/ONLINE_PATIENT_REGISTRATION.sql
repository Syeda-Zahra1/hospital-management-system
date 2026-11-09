-- Run once on an existing HMS database to enable online patient accounts.
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(20) NOT NULL
        CHECK (role IN ('admin', 'doctor', 'receptionist', 'pharmacist', 'patient')),
    patient_id INT UNIQUE REFERENCES patients(patient_id)
        ON DELETE CASCADE,
    CHECK ((role = 'patient' AND patient_id IS NOT NULL) OR
           (role <> 'patient' AND patient_id IS NULL))
);
