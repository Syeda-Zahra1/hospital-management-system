"""Create or refresh demo users in an explicitly enabled local/test database."""

import os

import psycopg2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

DEMO_USERS = (
    ("admin", "admin1234567", "System Admin", "admin"),
    ("dr.ahmed", "doctor1234567", "Dr. Ahmed Khan", "doctor"),
    ("reception1", "reception12345", "Fatima Receptionist", "receptionist"),
    ("pharmacy1", "pharmacy123456", "Ali Pharmacist", "pharmacist"),
    ("labtech1", "labtech123456", "Sadia Lab Technician", "labtech"),
    ("accountant1", "account123456", "Demo Accountant", "accountant"),
    ("hrmanager1", "hrmanager123", "Demo HR Manager", "hr_manager"),
    ("procure1", "procure123456", "Demo Procurement Officer", "procurement_officer"),
    ("branchmgr1", "branch123456", "Demo Branch Manager", "branch_manager"),
)


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must be configured before seeding demo users.")

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                for username, password, full_name, role in DEMO_USERS:
                    cur.execute(
                        """
                        INSERT INTO users (username, password_hash, full_name, role)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (username) DO UPDATE
                            SET password_hash = EXCLUDED.password_hash,
                                full_name     = EXCLUDED.full_name,
                                role          = EXCLUDED.role
                        """,
                        (username, generate_password_hash(password), full_name, role),
                    )
                    # Agar aapke paas user_sessions table hai, toh purane sessions revoke kar dein
                    try:
                        cur.execute(
                            """UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP
                               WHERE user_id = (SELECT user_id FROM users WHERE username = %s)
                                 AND revoked_at IS NULL""",
                            (username,),
                        )
                    except psycopg2.errors.UndefinedTable:
                        conn.rollback() # Agar table nahi hai toh ignore karein
                        # Re-insert since rollback aborts transaction
                        cur.execute(
                            """
                            INSERT INTO users (username, password_hash, full_name, role)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (username) DO UPDATE
                                SET password_hash = EXCLUDED.password_hash,
                                    full_name     = EXCLUDED.full_name,
                                    role          = EXCLUDED.role
                            """,
                            (username, generate_password_hash(password), full_name, role),
                        )
    finally:
        conn.close()

    print(f"✅ {len(DEMO_USERS)} demo users created or refreshed successfully.")


if __name__ == "__main__":
    main()

    