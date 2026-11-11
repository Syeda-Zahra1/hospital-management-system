"""Static, non-patient-specific help content for the HMS workflow assistant."""

KNOWLEDGE_BASE = """
SYSTEM OVERVIEW
The Hospital Management System (HMS) is a Flask web application for hospital
staff and patients. Staff sign in with their assigned account. The left
navigation menu shows pages available to the signed-in role. The assistant
can explain where features are and how workflows generally work. It cannot
look up or change any account, patient, appointment, bill, or clinical record.

MODULES AND NAVIGATION
- Dashboard (/): Staff see summary counts for patients, doctors, appointments,
  and medicines below reorder level. Patients are sent to their own portal.
- Patients (/patients): The directory lists patient demographics and contact
  details. Admins and receptionists can add patients. Admins can delete
  records. Doctors can view the directory but cannot add or delete here.
- Doctors (/doctors): Displays the doctor directory, specialization, and
  department. Only admins can see the salary column.
- Appointments (/appointments): Shows patient visits, dates, status, and
  reason. Admins and receptionists book appointments using a patient ID, doctor
  ID, date and time, and reason. Doctors can view appointments but cannot book
  them through the staff booking form.
- Medical Records (/medical_records): Admins and doctors can review diagnoses
  and prescription notes. They can create a prescription by selecting a
  patient, prescribing doctor, diagnosis, medicine, dosage, and quantity.
  Pharmacy staff then see pending prescriptions in the Pharmacy queue.
- Inventory (/inventory): Admins and pharmacists can see medicine quantities,
  reorder levels, and expiry dates. They can add medicine or update a quantity.
  “Reorder level” is the stock threshold used to flag medicine that may need
  replenishment; it does not place an order automatically.
- Pharmacy (/pharmacy): Admins and pharmacists review pending prescriptions.
  Dispensing updates inventory and marks the prescription dispensed when
  enough stock is available. If stock is insufficient, staff should review
  inventory and follow their clinic's replenishment process.
- Laboratory (/lab): Admins and doctors can place test orders. Admins and lab
  technicians can submit results for pending tests. Completed results appear
  in the test list.
- Rooms (/rooms): Admins and receptionists can see room status, admit an
  available patient to an available room, or discharge the current occupant.
- Billing (/billing): Admins and receptionists can create an invoice by
  entering the patient ID, amount, and payment status, then review invoices.
- Staff (/staff): Admins can add and view staff records.
- Admin Analytics (/admin/dashboard) and Audit Logs (/admin/logs): Admins can
  review analytics, low-stock alerts, and recent recorded system actions.
- Patient portal (/patient/dashboard): Patients can review only their own
  appointments, medical records, and bills, and request an appointment.

COMMON WORKFLOWS
To register a patient as staff, sign in with an admin or receptionist account,
open Patients, expand “Add a patient,” complete the required details, and save.
The separate public registration page lets a patient create their own account.

To book a staff appointment, open Appointments, expand the booking form, enter
the patient and doctor IDs, choose a date and time, optionally add a reason,
and submit. A patient can request a visit from their patient portal instead.

To dispense a prescription, open Pharmacy, check the patient, medicine, dosage,
and quantity, then choose Dispense. The system checks stock, reduces inventory,
and updates the prescription status. The assistant cannot inspect that
prescription or confirm that it was dispensed.

To order a laboratory test, an admin or doctor opens Laboratory, selects the
patient and doctor, enters the test name, and submits. An admin or lab
technician can enter a result for a pending order.

To admit a patient, an admin or receptionist opens Rooms, selects an available
patient on an available room card, and submits the admission. To free an
occupied room, use its Discharge action and confirm.

To create a bill, an admin or receptionist opens Billing, expands “Create an
invoice,” enters the patient ID, amount, and payment status, and submits.

ROLE SUMMARY
Admin: dashboard, patients, rooms, doctors, appointments, medical records,
inventory, pharmacy, laboratory, billing, staff, analytics, and audit logs.
Receptionist: dashboard, patients, rooms, doctors, appointments, and billing.
Doctor: dashboard, patients, doctors, appointments, medical records, and
laboratory. Pharmacist: dashboard, doctors, inventory, and pharmacy.
Lab technician: dashboard, doctors, and laboratory. Patient: personal
dashboard and doctor directory. Access is enforced by the application; ask an
administrator if a required page is not visible.

SAFETY BOUNDARY
Use this assistant only for HMS navigation and general workflows. Do not send
names, contact information, account details, medical details, or other patient
identifiers. The assistant has no database connection and cannot perform
actions. It is not a medical advisor. For clinical decisions, speak with a
licensed clinician; for account access, contact an HMS administrator.
"""
