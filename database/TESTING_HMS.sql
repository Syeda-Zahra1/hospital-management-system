SELECT p.first_name, p.last_name, d.first_name AS doctor, a.appointment_date, a.status
FROM appointments a
JOIN patients p ON a.patient_id = p.patient_id
JOIN doctors d ON a.doctor_id = d.doctor_id;

SELECT m.medicine_name, i.quantity, i.reorder_level
FROM inventory i JOIN medicines m ON i.medicine_id = m.medicine_id
WHERE i.quantity < i.reorder_level;