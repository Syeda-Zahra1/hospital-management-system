

"""Create or refresh demo users in an explicitly enabled local/test database."""

import os

import psycopg2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

DEMO_USERS = (
    ("admin", "HMS_DEMO_PASSWORD_ADMIN", "System Admin", "admin"),
    ("dr.ahmed", "HMS_DEMO_PASSWORD_DOCTOR", "Dr. Ahmed Khan", "doctor"),
    ("reception1", "HMS_DEMO_PASSWORD_RECEPTIONIST", "Fatima Receptionist", "receptionist"),
    ("pharmacy1", "HMS_DEMO_PASSWORD_PHARMACIST", "Ali Pharmacist", "pharmacist"),
    ("labtech1", "HMS_DEMO_PASSWORD_LABTECH", "Sadia Lab Technician", "labtech"),
    ("accountant1", "HMS_DEMO_PASSWORD_ACCOUNTANT", "Demo Accountant", "accountant"),
    ("hrmanager1", "HMS_DEMO_PASSWORD_HR_MANAGER", "Demo HR Manager", "hr_manager"),
    ("procure1", "HMS_DEMO_PASSWORD_PROCUREMENT", "Demo Procurement Officer", "procurement_officer"),
    ("branchmgr1", "HMS_DEMO_PASSWORD_BRANCH_MANAGER", "Demo Branch Manager", "branch_manager"),
)


def demo_users_from_environment(environ):
    if environ.get("HMS_ALLOW_DEMO_USERS", "").lower() != "true":
        raise ValueError(
            "Demo-user seeding is disabled. Set HMS_ALLOW_DEMO_USERS=true "
            "only for a local/test database."
        )

    users = []
    for username, password_key, full_name, role in DEMO_USERS:
        password = environ.get(password_key, "")
        if len(password) < 12:
            raise ValueError(f"{password_key} must be set to at least 12 characters.")
        users.append((username, password, full_name, role))
    return users


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must be configured before seeding demo users.")

    try:
        users = demo_users_from_environment(os.environ)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                for username, password, full_name, role in users:
                    cur.execute(
                        """
                        INSERT INTO users (username, password_hash, full_name, role)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (username) DO UPDATE
                            SET password_hash = EXCLUDED.password_hash,
                                full_name     = EXCLUDED.full_name,
                                role          = EXCLUDED.role,
                                is_active     = TRUE
                        """,
                        (username, generate_password_hash(password), full_name, role),
                    )
                    cur.execute(
                        """UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP
                           WHERE user_id = (SELECT user_id FROM users WHERE username = %s)
                             AND revoked_at IS NULL""",
                        (username,),
                    )
    finally:
        conn.close()

    print(f"{len(users)} demo users created or refreshed successfully.")


if __name__ == "__main__":
    main()


