

"""
Creates demo users for the Hospital Management System.

Run this ONCE after creating the schema, or anytime you want to
reset demo passwords. Safe to re-run: existing usernames get their
password hash and role refreshed.

DEMO CREDENTIALS ONLY — change these before any real deployment.
"""

import os

import psycopg2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

# Demo users: (username, plain_password, full_name, role)
users = [
    ('admin',      'admin123',  'System Admin',        'admin'),
    ('dr.ahmed',   'doc123',    'Dr. Ahmed Khan',      'doctor'),
    ('reception1', 'rec123',    'Fatima Receptionist', 'receptionist'),
    ('pharmacy1',  'pharm123',  'Ali Pharmacist',      'pharmacist'),
    ('labtech1',   'lab123',    'Sadia Lab Technician','labtech'),
]

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

for username, password, full_name, role in users:
    hashed = generate_password_hash(password)
    cur.execute(
        """
        INSERT INTO users (username, password_hash, full_name, role)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (username) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                full_name     = EXCLUDED.full_name,
                role          = EXCLUDED.role
        """,
        (username, hashed, full_name, role),
    )

conn.commit()
cur.close()
conn.close()

print(f"✅ {len(users)} users created/updated successfully!")


