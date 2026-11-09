# we use this for generating paswords


from werkzeug.security import generate_password_hash
import psycopg2

conn = psycopg2.connect(host="localhost", database="HMS",
                         user="postgres", password="Malaika123", port="5432")
cur = conn.cursor()

users = [
    ('admin',      'admin123',  'System Admin',        'admin'),
    ('dr.ahmed',   'doc123',    'Dr. Ahmed Khan',      'doctor'),
    ('reception1', 'rec123',    'Fatima Receptionist', 'receptionist'),
    ('pharmacy1',  'pharm123',  'Ali Pharmacist',      'pharmacist'),
]

for username, pwd, name, role in users:
    hashed = generate_password_hash(pwd)
    cur.execute("""INSERT INTO users (username, password_hash, full_name, role)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (username) DO NOTHING""",
                (username, hashed, name, role))

conn.commit()
cur.close()
conn.close()
print("✅ Users created successfully!")


