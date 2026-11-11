-- ============================================================
-- HOSPITAL MANAGEMENT SYSTEM — SCHEMA (consolidated)
-- Run on an EMPTY database, in order, top to bottom.
-- ============================================================

-- ---------- 1. DEPARTMENTS ----------
CREATE TABLE departments (
    dept_id     SERIAL PRIMARY KEY,
    dept_name   VARCHAR(100) NOT NULL UNIQUE,
    location    VARCHAR(100),
    phone       VARCHAR(20)
);

-- ---------- 2. DOCTORS ----------
CREATE TABLE doctors (
    doctor_id       SERIAL PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    specialization  VARCHAR(100),
    email           VARCHAR(100) UNIQUE,
    phone           VARCHAR(20),
    dept_id         INT REFERENCES departments(dept_id) ON DELETE SET NULL,
    hire_date       DATE DEFAULT CURRENT_DATE,
    salary          NUMERIC(10,2)
);

-- ---------- 3. PATIENTS ----------
CREATE TABLE patients (
    patient_id          SERIAL PRIMARY KEY,
    first_name          VARCHAR(50) NOT NULL,
    last_name           VARCHAR(50) NOT NULL,
    dob                 DATE,
    gender              VARCHAR(10),
    phone               VARCHAR(20),
    email               VARCHAR(100),
    address             TEXT,
    blood_group         VARCHAR(5),
    registration_date   DATE DEFAULT CURRENT_DATE
);

-- ---------- 4. ROOMS ----------
CREATE TABLE rooms (
    room_id             SERIAL PRIMARY KEY,
    room_number         VARCHAR(10) UNIQUE NOT NULL,
    room_type           VARCHAR(50),
    charges_per_day     NUMERIC(10,2),
    status              VARCHAR(20) DEFAULT 'Available',
    current_patient_id  INT REFERENCES patients(patient_id) ON DELETE SET NULL
);

-- ---------- 5. APPOINTMENTS ----------
CREATE TABLE appointments (
    appointment_id      SERIAL PRIMARY KEY,
    patient_id          INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id           INT REFERENCES doctors(doctor_id)  ON DELETE CASCADE,
    appointment_date    TIMESTAMP NOT NULL,
    status              VARCHAR(20) DEFAULT 'Scheduled',
    reason              TEXT,
    booked_by           VARCHAR(20) DEFAULT 'Staff'
);

-- ---------- 6. MEDICAL RECORDS ----------
CREATE TABLE medical_records (
    record_id       SERIAL PRIMARY KEY,
    patient_id      INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id       INT REFERENCES doctors(doctor_id)   ON DELETE SET NULL,
    diagnosis       TEXT,
    prescription    TEXT,
    visit_date      DATE DEFAULT CURRENT_DATE
);

-- ---------- 7. MEDICINES ----------
CREATE TABLE medicines (
    medicine_id     SERIAL PRIMARY KEY,
    medicine_name   VARCHAR(100) NOT NULL,
    manufacturer    VARCHAR(100),
    price           NUMERIC(10,2),
    expiry_date     DATE
);

-- ---------- 8. INVENTORY ----------
CREATE TABLE inventory (
    inventory_id    SERIAL PRIMARY KEY,
    medicine_id     INT REFERENCES medicines(medicine_id) ON DELETE CASCADE,
    quantity        INT DEFAULT 0,
    reorder_level   INT DEFAULT 10,
    last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 9. BILLING ----------
CREATE TABLE billing (
    bill_id         SERIAL PRIMARY KEY,
    patient_id      INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    total_amount    NUMERIC(10,2),
    payment_status  VARCHAR(20) DEFAULT 'Pending',
    bill_date       DATE DEFAULT CURRENT_DATE
);

-- ---------- 10. STAFF ----------
CREATE TABLE staff (
    staff_id    SERIAL PRIMARY KEY,
    first_name  VARCHAR(50),
    last_name   VARCHAR(50),
    role        VARCHAR(50),
    phone       VARCHAR(20),
    email       VARCHAR(100),
    dept_id     INT REFERENCES departments(dept_id) ON DELETE SET NULL,
    salary      NUMERIC(10,2)
);

-- ---------- 11. USERS (staff + patients) ----------
-- password_hash is TEXT because scrypt hashes exceed 255 chars.
-- username is VARCHAR(150) so email logins fit comfortably.
CREATE TABLE users (
    user_id         SERIAL PRIMARY KEY,
    username        VARCHAR(150) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(150) NOT NULL,
    role            VARCHAR(20) NOT NULL
                    CHECK (role IN ('admin','doctor','receptionist',
                                    'pharmacist','labtech','patient')),
    patient_id      INT UNIQUE REFERENCES patients(patient_id) ON DELETE CASCADE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK ((role =  'patient' AND patient_id IS NOT NULL) OR
           (role <> 'patient' AND patient_id IS NULL))
);

-- ---------- 12. PRESCRIPTIONS ----------
CREATE TABLE prescriptions (
    prescription_id SERIAL PRIMARY KEY,
    record_id       INT REFERENCES medical_records(record_id) ON DELETE CASCADE,
    medicine_id     INT REFERENCES medicines(medicine_id),
    dosage          VARCHAR(50),
    quantity        INT DEFAULT 1,
    status          VARCHAR(20) DEFAULT 'Pending'
);

-- ---------- 13. LAB TESTS ----------
CREATE TABLE lab_tests (
    test_id     SERIAL PRIMARY KEY,
    patient_id  INT REFERENCES patients(patient_id),
    doctor_id   INT REFERENCES doctors(doctor_id),
    test_name   VARCHAR(100) NOT NULL,
    result      TEXT,
    status      VARCHAR(20) DEFAULT 'Pending',
    test_date   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 14. AUDIT LOGS ----------
CREATE TABLE audit_logs (
    log_id      SERIAL PRIMARY KEY,
    user_id     INT,
    username    VARCHAR(50),
    action      VARCHAR(255),
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

