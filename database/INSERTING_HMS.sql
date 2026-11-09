-- Departments
INSERT INTO departments (dept_name, location, phone) VALUES
('Cardiology', 'Block A - 2nd Floor', '0300-1111111'),
('Neurology', 'Block B - 1st Floor', '0300-2222222'),
('Orthopedics', 'Block C - Ground', '0300-3333333'),
('Pediatrics', 'Block A - 3rd Floor', '0300-4444444'),
('Emergency', 'Block D - Ground', '0300-5555555');

-- Doctors
INSERT INTO doctors (first_name, last_name, specialization, email, phone, dept_id, salary) VALUES
('Ahmed', 'Khan', 'Cardiologist', 'ahmed.khan@hospital.com', '0301-1111111', 1, 250000),
('Sara', 'Ali', 'Neurologist', 'sara.ali@hospital.com', '0301-2222222', 2, 230000),
('Bilal', 'Hussain', 'Orthopedic Surgeon', 'bilal.h@hospital.com', '0301-3333333', 3, 240000),
('Ayesha', 'Malik', 'Pediatrician', 'ayesha.m@hospital.com', '0301-4444444', 4, 200000),
('Usman', 'Tariq', 'Emergency Physician', 'usman.t@hospital.com', '0301-5555555', 5, 220000);

-- Patients
INSERT INTO patients (first_name, last_name, dob, gender, phone, email, address, blood_group) VALUES
('Hassan', 'Raza', '1990-05-14', 'Male', '0311-1111111', 'hassan@email.com', 'Lahore', 'A+'),
('Fatima', 'Noor', '1985-08-22', 'Female', '0311-2222222', 'fatima@email.com', 'Karachi', 'B+'),
('Ali', 'Ahmad', '2000-01-10', 'Male', '0311-3333333', 'ali@email.com', 'Islamabad', 'O+'),
('Zainab', 'Sheikh', '1995-11-30', 'Female', '0311-4444444', 'zainab@email.com', 'Multan', 'AB+'),
('Hamza', 'Iqbal', '1978-07-05', 'Male', '0311-5555555', 'hamza@email.com', 'Faisalabad', 'A-');

-- Rooms
INSERT INTO rooms (room_number, room_type, charges_per_day, status) VALUES
('101', 'General', 3000, 'Available'),
('102', 'Private', 8000, 'Occupied'),
('201', 'ICU', 15000, 'Available'),
('202', 'Semi-Private', 5000, 'Available'),
('301', 'VIP', 20000, 'Occupied');

-- Appointments
INSERT INTO appointments (patient_id, doctor_id, appointment_date, status, reason) VALUES
(1, 1, '2025-01-15 10:00:00', 'Scheduled', 'Chest pain'),
(2, 2, '2025-01-16 11:30:00', 'Completed', 'Headache'),
(3, 3, '2025-01-17 09:00:00', 'Scheduled', 'Fracture checkup'),
(4, 4, '2025-01-18 14:00:00', 'Scheduled', 'Child fever'),
(5, 5, '2025-01-19 16:00:00', 'Cancelled', 'Emergency');

-- Medical Records
INSERT INTO medical_records (patient_id, doctor_id, diagnosis, prescription) VALUES
(1, 1, 'Mild angina', 'Aspirin 75mg daily'),
(2, 2, 'Migraine', 'Sumatriptan 50mg'),
(3, 3, 'Hairline fracture', 'Cast + Calcium'),
(4, 4, 'Viral fever', 'Paracetamol syrup'),
(5, 5, 'Hypertension', 'Amlodipine 5mg');

-- Medicines
INSERT INTO medicines (medicine_name, manufacturer, price, expiry_date) VALUES
('Paracetamol', 'GSK', 50, '2026-12-31'),
('Aspirin', 'Bayer', 80, '2026-06-30'),
('Amoxicillin', 'Pfizer', 150, '2025-12-31'),
('Sumatriptan', 'Novartis', 300, '2026-03-31'),
('Amlodipine', 'Getz', 120, '2027-01-31');

-- Inventory
INSERT INTO inventory (medicine_id, quantity, reorder_level) VALUES
(1, 500, 50),
(2, 300, 40),
(3, 20, 30),
(4, 100, 20),
(5, 250, 25);

-- Billing
INSERT INTO billing (patient_id, total_amount, payment_status) VALUES
(1, 15000, 'Paid'),
(2, 8000, 'Pending'),
(3, 12000, 'Paid'),
(4, 5000, 'Pending'),
(5, 25000, 'Paid');

-- Staff
INSERT INTO staff (first_name, last_name, role, phone, email, dept_id, salary) VALUES
('Nadia', 'Javed', 'Nurse', '0321-1111111', 'nadia@hospital.com', 1, 60000),
('Kamran', 'Shah', 'Receptionist', '0321-2222222', 'kamran@hospital.com', 5, 45000),
('Sadia', 'Yousaf', 'Lab Technician', '0321-3333333', 'sadia@hospital.com', 2, 55000),
('Imran', 'Baig', 'Ward Boy', '0321-4444444', 'imran@hospital.com', 3, 35000),
('Rabia', 'Anwar', 'Pharmacist', '0321-5555555', 'rabia@hospital.com', 1, 70000);