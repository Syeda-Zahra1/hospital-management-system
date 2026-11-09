-- ==========================================
-- INDEXES
-- ==========================================

CREATE INDEX idx_doctors_dept
ON doctors(dept_id);

CREATE INDEX idx_staff_dept
ON staff(dept_id);

CREATE INDEX idx_appointments_patient
ON appointments(patient_id);

CREATE INDEX idx_appointments_doctor
ON appointments(doctor_id);

CREATE INDEX idx_appointments_date
ON appointments(appointment_date);

CREATE INDEX idx_appointments_status_date
ON appointments(status, appointment_date);

CREATE INDEX idx_medical_records_patient
ON medical_records(patient_id);

CREATE INDEX idx_medical_records_doctor
ON medical_records(doctor_id);

CREATE INDEX idx_medical_records_date
ON medical_records(visit_date);

CREATE INDEX idx_inventory_medicine
ON inventory(medicine_id);

CREATE INDEX idx_inventory_quantity
ON inventory(quantity);

CREATE INDEX idx_billing_patient
ON billing(patient_id);

CREATE INDEX idx_billing_status_date
ON billing(payment_status, bill_date);

CREATE INDEX idx_medicines_expiry
ON medicines(expiry_date);