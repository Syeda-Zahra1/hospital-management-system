import os
import secrets
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from psycopg2.extras import RealDictCursor

from werkzeug.security import check_password_hash
from functools import wraps

from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

# ---------- HELPER FUNCTIONS ----------
def log_action(action):
    """Logs user actions into the audit_logs table."""
    if 'username' in session:
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO audit_logs (user_id, username, action) VALUES (%s, %s, %s)",
                    (session.get('user_id'), session.get('username'), action))
        conn.commit(); cur.close(); conn.close()

# ----- AUTH DECORATORS -----
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login first.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please login first.", "error")
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                flash("⛔ Access Denied — You are not authorized.", "error")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# Database connection
def get_db():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        connect_timeout=10
    )

# ---------- HOME / DASHBOARD ----------
@app.route("/")
@login_required 
def index():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT COUNT(*) AS c FROM patients"); patients = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM doctors"); doctors = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM appointments"); appts = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM inventory WHERE quantity < reorder_level"); low = cur.fetchone()['c']
    cur.close(); conn.close()
    return render_template("index.html", patients=patients, doctors=doctors, appts=appts, low=low)

# ---------- PATIENTS ----------
@app.route("/patients")
@login_required 
def patients():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM patients ORDER BY patient_id DESC")
    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("patients.html", patients=data)

@app.route("/patients/add", methods=["POST"])
@role_required('admin', 'receptionist')
def add_patient():
    f = request.form
    conn = get_db(); cur = conn.cursor()
    cur.execute("""INSERT INTO patients (first_name,last_name,dob,gender,phone,email,address,blood_group)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (f['first_name'], f['last_name'], f['dob'], f['gender'],
                 f['phone'], f['email'], f['address'], f['blood_group']))
    conn.commit(); cur.close(); conn.close()
    
    log_action(f"Added new patient: {f['first_name']} {f['last_name']}")
    flash("Patient added successfully!", "success")
    return redirect(url_for("patients"))

@app.route("/patients/delete/<int:pid>")
@role_required('admin')
def delete_patient(pid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM patients WHERE patient_id=%s", (pid,))
    conn.commit(); cur.close(); conn.close()
    
    log_action(f"Deleted patient ID {pid}")
    flash("Patient deleted.", "success")
    return redirect(url_for("patients"))

# ---------- PATIENT PORTAL ----------
@app.route('/patient/dashboard')
@role_required('patient') 
def patient_dashboard():
    patient_id = session['patient_id']
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
    patient = cur.fetchone()
    
    cur.execute("""SELECT a.*, d.first_name || ' ' || d.last_name AS doctor_name, dp.dept_name
                   FROM appointments a
                   JOIN doctors d ON a.doctor_id = d.doctor_id
                   LEFT JOIN departments dp ON d.dept_id = dp.dept_id
                   WHERE a.patient_id = %s ORDER BY a.appointment_date DESC""", (patient_id,))
    appointments = cur.fetchall()
    
    cur.execute("""SELECT m.*, d.first_name || ' ' || d.last_name AS doctor_name
                   FROM medical_records m
                   JOIN doctors d ON m.doctor_id = d.doctor_id
                   WHERE m.patient_id = %s ORDER BY m.visit_date DESC""", (patient_id,))
    records = cur.fetchall()
    
    cur.execute("SELECT * FROM billing WHERE patient_id = %s", (patient_id,))
    bills = cur.fetchall()
    
    cur.close(); conn.close()
    return render_template("Patient_Dashboard.html", patient=patient, appointments=appointments, records=records, bills=bills)

@app.route('/patient/book_appointment', methods=['POST'])
@role_required('patient')
def patient_book_appointment():
    f = request.form
    patient_id = session['patient_id']
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("""INSERT INTO appointments (patient_id, doctor_id, appointment_date, reason, status, booked_by)
                   VALUES (%s, %s, %s, %s, 'Scheduled', 'Patient')""",
                (patient_id, f['doctor_id'], f['appointment_date'], f['reason']))
    conn.commit(); cur.close(); conn.close()
    
    log_action(f"Patient self-booked appointment with doctor ID {f['doctor_id']}")
    flash("✅ Your appointment has been requested successfully!", "success")
    return redirect(url_for('patient_dashboard'))

# ---------- DOCTORS ----------
@app.route("/doctors")
@login_required 
def doctors():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT d.*, dp.dept_name FROM doctors d
                   LEFT JOIN departments dp ON d.dept_id = dp.dept_id
                   ORDER BY d.doctor_id DESC""")
    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("doctors.html", doctors=data)

# ---------- MEDICAL RECORDS & PRESCRIPTIONS ----------
@app.route("/medical_records")
@login_required
def medical_records():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT mr.*, p.first_name || ' ' || p.last_name AS patient_name,
               d.first_name || ' ' || d.last_name AS doctor_name
        FROM medical_records mr
        JOIN patients p ON mr.patient_id = p.patient_id
        LEFT JOIN doctors d ON mr.doctor_id = d.doctor_id
        ORDER BY mr.visit_date DESC
    """)
    records = cur.fetchall()
    cur.close(); conn.close()
    return render_template('medical_records.html', records=records)

@app.route('/doctor/add_prescription', methods=['POST'])
@role_required('admin', 'doctor')
def add_prescription():
    f = request.form
    conn = get_db(); cur = conn.cursor()
    
    cur.execute("""INSERT INTO medical_records (patient_id, doctor_id, diagnosis, prescription) 
                   VALUES (%s, %s, %s, %s) RETURNING record_id""",
                (f['patient_id'], f['doctor_id'], f['diagnosis'], "See attached medicines"))
    record_id = cur.fetchone()[0]
    
    cur.execute("""INSERT INTO prescriptions (record_id, medicine_id, dosage) 
                   VALUES (%s, %s, %s)""",
                (record_id, f['medicine_id'], f['dosage']))
    
    conn.commit(); cur.close(); conn.close()
    log_action(f"Doctor ID {f['doctor_id']} prescribed medicine ID {f['medicine_id']}")
    flash("✅ Prescription sent to Pharmacy!", "success")
    return redirect(url_for('medical_records'))

# ---------- APPOINTMENTS ----------
@app.route("/appointments")
@login_required 
def appointments():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT a.*, p.first_name || ' ' || p.last_name AS patient_name,
                          d.first_name || ' ' || d.last_name AS doctor_name
                   FROM appointments a
                   JOIN patients p ON a.patient_id = p.patient_id
                   JOIN doctors d ON a.doctor_id = d.doctor_id
                   ORDER BY a.appointment_date DESC""")
    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("appointments.html", appointments=data)

@app.route("/appointments/add", methods=["POST"])
@role_required('admin', 'receptionist')
def add_appointment():
    f = request.form
    conn = get_db(); cur = conn.cursor()
    cur.execute("""INSERT INTO appointments (patient_id, doctor_id, appointment_date, reason)
                   VALUES (%s,%s,%s,%s)""",
                (f['patient_id'], f['doctor_id'], f['appointment_date'], f['reason']))
    conn.commit(); cur.close(); conn.close()
    log_action(f"Staff booked appointment for patient ID {f['patient_id']}")
    flash("Appointment booked!", "success")
    return redirect(url_for("appointments"))

# ---------- INVENTORY & PHARMACY ----------
@app.route("/inventory")
@login_required 
def inventory():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT i.*, m.medicine_name, m.price, m.expiry_date
                   FROM inventory i JOIN medicines m ON i.medicine_id = m.medicine_id
                   ORDER BY i.inventory_id""")
    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("inventory.html", inventory=data)

@app.route("/inventory/update/<int:iid>", methods=["POST"])
@role_required('admin', 'pharmacist')
def update_inventory(iid):
    qty = request.form['quantity']
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE inventory SET quantity=%s, last_updated=NOW() WHERE inventory_id=%s", (qty, iid))
    conn.commit(); cur.close(); conn.close()
    log_action(f"Updated inventory ID {iid} to quantity {qty}")
    flash("Inventory updated!", "success")
    return redirect(url_for("inventory"))

@app.route("/medicines/add", methods=["POST"])
@role_required('admin', 'pharmacist')
def add_medicine():
    f = request.form
    conn = get_db(); cur = conn.cursor()
    
    cur.execute("""INSERT INTO medicines (medicine_name, manufacturer, price, expiry_date)
                   VALUES (%s, %s, %s, %s) RETURNING medicine_id""",
                (f['medicine_name'], f['manufacturer'], f['price'], f['expiry_date']))
    med_id = cur.fetchone()[0]
    
    cur.execute("""INSERT INTO inventory (medicine_id, quantity, reorder_level)
                   VALUES (%s, %s, %s)""",
                (med_id, f['quantity'], f['reorder_level']))
    
    conn.commit(); cur.close(); conn.close()
    log_action(f"Added new medicine: {f['medicine_name']}")
    flash("Medicine added to inventory successfully!", "success")
    return redirect(url_for("inventory"))

@app.route('/pharmacy')
@role_required('admin', 'pharmacist') 
def pharmacy_dashboard():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT pr.prescription_id, pr.dosage, m.medicine_name, m.medicine_id,
               pat.first_name || ' ' || pat.last_name AS patient_name,
               doc.first_name || ' ' || doc.last_name AS doctor_name,
               mr.diagnosis
        FROM prescriptions pr
        JOIN medicines m ON pr.medicine_id = m.medicine_id
        JOIN medical_records mr ON pr.record_id = mr.record_id
        JOIN patients pat ON mr.patient_id = pat.patient_id
        JOIN doctors doc ON mr.doctor_id = doc.doctor_id
        WHERE pr.status = 'Pending'
        ORDER BY pr.prescription_id DESC
    """)
    pending_prescriptions = cur.fetchall()
    cur.close(); conn.close()
    return render_template('Pharmacy.html', prescriptions=pending_prescriptions)

@app.route('/pharmacy/dispense/<int:prescription_id>/<int:medicine_id>')
@role_required('admin', 'pharmacist')
def dispense_medicine(prescription_id, medicine_id):
    conn = get_db(); cur = conn.cursor()
    
    cur.execute("SELECT quantity FROM inventory WHERE medicine_id = %s", (medicine_id,))
    stock = cur.fetchone()
    
    if stock and stock[0] > 0:
        cur.execute("UPDATE inventory SET quantity = quantity - 1, last_updated = NOW() WHERE medicine_id = %s", (medicine_id,))
        cur.execute("UPDATE prescriptions SET status = 'Dispensed' WHERE prescription_id = %s", (prescription_id,))
        conn.commit()
        log_action(f"Dispensed prescription ID {prescription_id} (Medicine ID {medicine_id})")
        flash("✅ Medicine dispensed and inventory updated!", "success")
    else:
        flash("❌ Out of Stock! Cannot dispense.", "error")
        
    cur.close(); conn.close()
    return redirect(url_for('pharmacy_dashboard'))

# ---------- BILLING ----------
@app.route("/billing")
@login_required 
def billing():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT b.*, p.first_name || ' ' || p.last_name AS patient_name
                   FROM billing b JOIN patients p ON b.patient_id = p.patient_id
                   ORDER BY b.bill_id DESC""")
    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("billing.html", bills=data)

# ---------- STAFF ----------
@app.route("/staff")
@role_required('admin')
def staff():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT s.*, d.dept_name FROM staff s
                   LEFT JOIN departments d ON s.dept_id = d.dept_id""")
    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("staff.html", staff=data)

# ---------- ROOM MANAGEMENT ----------
@app.route('/rooms')
@role_required('admin', 'receptionist')
def rooms_dashboard():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT r.*, p.first_name || ' ' || p.last_name AS patient_name
        FROM rooms r
        LEFT JOIN patients p ON r.current_patient_id = p.patient_id
        ORDER BY r.room_number
    """)
    rooms = cur.fetchall()
    cur.execute("""
        SELECT * FROM patients 
        WHERE patient_id NOT IN (SELECT current_patient_id FROM rooms WHERE current_patient_id IS NOT NULL)
    """)
    available_patients = cur.fetchall()
    cur.close(); conn.close()
    return render_template('Rooms.html', rooms=rooms, patients=available_patients)

@app.route('/rooms/admit/<int:room_id>', methods=['POST'])
@role_required('admin', 'receptionist')
def admit_patient(room_id):
    patient_id = request.form['patient_id']
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE rooms SET status = 'Occupied', current_patient_id = %s WHERE room_id = %s", (patient_id, room_id))
    conn.commit(); cur.close(); conn.close()
    log_action(f"Admitted patient ID {patient_id} to room ID {room_id}")
    flash("✅ Patient admitted to room successfully!", "success")
    return redirect(url_for('rooms_dashboard'))

@app.route('/rooms/discharge/<int:room_id>')
@role_required('admin', 'receptionist')
def discharge_patient(room_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE rooms SET status = 'Available', current_patient_id = NULL WHERE room_id = %s", (room_id,))
    conn.commit(); cur.close(); conn.close()
    log_action(f"Discharged patient from room ID {room_id}")
    flash("✅ Patient discharged. Room is now available.", "success")
    return redirect(url_for('rooms_dashboard'))

# ---------- LAB DASHBOARD ----------
@app.route('/lab')
@role_required('admin', 'labtech', 'doctor')
def lab_dashboard():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT lt.*, p.first_name || ' ' || p.last_name AS patient_name,
               d.first_name || ' ' || d.last_name AS doctor_name
        FROM lab_tests lt
        JOIN patients p ON lt.patient_id = p.patient_id
        LEFT JOIN doctors d ON lt.doctor_id = d.doctor_id
        ORDER BY lt.status DESC, lt.test_date DESC
    """)
    tests = cur.fetchall()
    cur.execute("SELECT patient_id, first_name, last_name FROM patients")
    patients = cur.fetchall()
    cur.execute("SELECT doctor_id, first_name, last_name FROM doctors")
    doctors = cur.fetchall()
    cur.close(); conn.close()
    return render_template('Lab.html', tests=tests, patients=patients, doctors=doctors)

@app.route('/lab/order', methods=['POST'])
@role_required('admin', 'doctor')
def order_lab_test():
    f = request.form
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO lab_tests (patient_id, doctor_id, test_name) VALUES (%s, %s, %s)",
                (f['patient_id'], f['doctor_id'], f['test_name']))
    conn.commit(); cur.close(); conn.close()
    log_action(f"Ordered lab test '{f['test_name']}' for patient ID {f['patient_id']}")
    flash("🧪 Lab test ordered successfully!", "success")
    return redirect(url_for('lab_dashboard'))

@app.route('/lab/submit/<int:test_id>', methods=['POST'])
@role_required('admin', 'labtech')
def submit_lab_result(test_id):
    result = request.form['result']
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE lab_tests SET result = %s, status = 'Completed' WHERE test_id = %s", (result, test_id))
    conn.commit(); cur.close(); conn.close()
    log_action(f"Submitted result for lab test ID {test_id}")
    flash("✅ Lab result submitted!", "success")
    return redirect(url_for('lab_dashboard'))

# ---------- ADMIN DASHBOARD & LOGS ----------
@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT m.medicine_name, i.quantity 
                   FROM inventory i JOIN medicines m ON i.medicine_id = m.medicine_id
                   WHERE i.quantity < i.reorder_level""")
    low_stock_data = cur.fetchall()
    cur.close(); conn.close()
    return render_template('admin_dashboard.html', low_stock_data=low_stock_data)

@app.route('/admin/analytics')
@role_required('admin')
def admin_analytics():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT SUM(total_amount) as total FROM billing WHERE payment_status = 'Paid'")
    revenue = cur.fetchone()['total'] or 0
    cur.execute("""
        SELECT TO_CHAR(registration_date, 'Mon YYYY') as month, COUNT(*) as count
        FROM patients
        GROUP BY TO_CHAR(registration_date, 'Mon YYYY'), MIN(registration_date)
        ORDER BY MIN(registration_date) DESC LIMIT 6
    """)
    patient_data = cur.fetchall()
    cur.execute("SELECT status, COUNT(*) as count FROM appointments GROUP BY status")
    appt_data = cur.fetchall()
    cur.execute("""
        SELECT m.medicine_name, i.quantity 
        FROM inventory i JOIN medicines m ON i.medicine_id = m.medicine_id
        WHERE i.quantity < i.reorder_level
    """)
    low_stock = cur.fetchall()
    cur.close(); conn.close()
    return {"revenue": revenue, "patients": patient_data, "appointments": appt_data, "low_stock": low_stock}

@app.route('/admin/logs')
@role_required('admin')
def admin_logs():
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100")
    logs = cur.fetchall()
    cur.close(); conn.close()
    return render_template('logs.html', logs=logs)

# ---------- AUTHENTICATION (LOGIN/LOGOUT/REGISTER) ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']

        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close(); conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            
            if user['role'] == 'patient':
                session['patient_id'] = user['patient_id']
                flash(f"Welcome back, {user['full_name']}! 👋", "success")
                return redirect(url_for('patient_dashboard'))
            else:
                flash(f"Welcome, {user['full_name']}! 👋", "success")
                return redirect(url_for('index'))
        else:
            flash("❌ Invalid username or password.", "error")

    return render_template('Login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        f = request.form
        first_name = f.get('first_name', '').strip()
        last_name = f.get('last_name', '').strip()
        dob = f.get('dob', '').strip()
        gender = f.get('gender', '').strip()
        phone = f.get('phone', '').strip()
        address = f.get('address', '').strip()
        email = f.get('email', '').strip().lower()
        password = f.get('password', '')
        blood_group = f.get('blood_group', '').strip()
        email_parts = email.split('@')

        if (not first_name or not last_name or not phone or len(email_parts) != 2 or
                not all(email_parts) or any(character.isspace() for character in email) or
                len(first_name) > 50 or len(last_name) > 50 or len(phone) > 20 or
                len(email) > 100 or len(blood_group) > 5):
            flash("Enter your name, a valid email address, and phone number.", "error")
            return render_template('Register.html'), 400
        if gender not in {'Male', 'Female', 'Other'}:
            flash("Choose a valid gender option.", "error")
            return render_template('Register.html'), 400
        if len(password) < 8:
            flash("Your password must be at least 8 characters long.", "error")
            return render_template('Register.html'), 400
        try:
            birth_date = date.fromisoformat(dob)
        except ValueError:
            flash("Enter a valid date of birth.", "error")
            return render_template('Register.html'), 400
        if birth_date >= date.today():
            flash("Date of birth must be in the past.", "error")
            return render_template('Register.html'), 400

        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO patients (first_name, last_name, dob, gender, phone, email, address, blood_group)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING patient_id""",
                            (first_name, last_name, birth_date, gender, phone, email, address, blood_group or None))
                new_patient_id = cur.fetchone()[0]

                cur.execute("""INSERT INTO users (username, password_hash, full_name, role, patient_id)
                               VALUES (%s, %s, %s, 'patient', %s) RETURNING user_id""",
                            (email, generate_password_hash(password), f"{first_name} {last_name}", new_patient_id))
                new_user_id = cur.fetchone()[0]
            conn.commit()

            session.clear()
            session['user_id'] = new_user_id
            session['username'] = email
            session['full_name'] = f"{first_name} {last_name}"
            session['role'] = 'patient'
            session['patient_id'] = new_patient_id

            log_action(f"New patient self-registered: {first_name} {last_name}")
            flash("Registration successful! Welcome to the Patient Portal.", "success")
            return redirect(url_for('patient_dashboard'))

        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            flash("An account with this email already exists. Please log in instead.", "error")
            return render_template('Register.html'), 409
        finally:
            conn.close()

    return render_template('Register.html')


@app.route("/billing/add", methods=["POST"])
@role_required('admin', 'receptionist')
def add_bill():
    f = request.form
    conn = get_db(); cur = conn.cursor()
    
    cur.execute("""INSERT INTO billing (patient_id, total_amount, payment_status)
                   VALUES (%s, %s, %s)""",
                (f['patient_id'], f['total_amount'], f['payment_status']))
    
    conn.commit(); cur.close(); conn.close()
    
    log_action(f"Created a bill of Rs. {f['total_amount']} for patient ID {f['patient_id']}")
    flash("Bill added successfully!", "success")
    return redirect(url_for("billing"))

@app.route("/staff/add", methods=["POST"])
@role_required('admin')
def add_staff():
    f = request.form
    conn = get_db(); cur = conn.cursor()
    cur.execute("""INSERT INTO staff (first_name, last_name, role, phone, email, dept_id, salary)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (f['first_name'], f['last_name'], f['role'], f['phone'], f['email'], f['dept_id'], f['salary']))
    conn.commit(); cur.close(); conn.close()
    log_action(f"Added new staff member: {f['first_name']} {f['last_name']}")
    flash("Staff member added successfully!", "success")
    return redirect(url_for("staff"))


if __name__ == "__main__":
    app.run(debug=True)