-- Appointment details
-- Displays patient names, doctor names, departments, appointment dates, and statuses.

CREATE VIEW v_appointment_details AS
SELECT
    a.appointment_id,
    p.patient_id,
    p.first_name || ' ' || p.last_name
        AS patient_name,
    d.doctor_id,
    d.first_name || ' ' || d.last_name
        AS doctor_name,
    d.specialization,
    dep.dept_name AS department_name,
    a.appointment_date,
    a.status,
    a.reason
FROM appointments a
JOIN patients p
    ON a.patient_id = p.patient_id
JOIN doctors d
    ON a.doctor_id = d.doctor_id
LEFT JOIN departments dep
    ON d.dept_id = dep.dept_id;

-- Patient medical history
-- Displays each patient's diagnoses, prescriptions, visit dates, and treating doctor where available.

CREATE VIEW v_patient_medical_history AS
SELECT
    mr.record_id,
    p.patient_id,
    p.first_name || ' ' || p.last_name
        AS patient_name,
    d.first_name || ' ' || d.last_name
        AS doctor_name,
    mr.diagnosis,
    mr.prescription,
    mr.visit_date
FROM medical_records mr
JOIN patients p
    ON mr.patient_id = p.patient_id
LEFT JOIN doctors d
    ON mr.doctor_id = d.doctor_id;