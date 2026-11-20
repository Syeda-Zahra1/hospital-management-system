# Hospital Management System

A Flask and PostgreSQL web application for common hospital administration workflows. The app uses Jinja templates to render the interface on the server and provides separate access for staff and patients.

## Features

- Sign-in, patient self-registration, hashed passwords, and role-based access.
- Role-specific dashboards and navigation for administrators, doctors, receptionists, pharmacists, laboratory technicians, and patients.
- Patient and doctor directories, appointments, medical records, and prescriptions.
- Administrators can add doctor and staff records by selecting a department using its name and ID.
- Medicine inventory, pharmacy dispensing, laboratory tests, room admission/discharge, and billing.
- Administrator analytics and audit logs.
- Patient portal for viewing personal appointments, records, and bills. Patients can request appointments by selecting a doctor by name.
- Optional HMS workflow help chatbot for administrators and receptionists. It is disabled until a Groq API key is configured.

The chatbot is for general HMS workflow guidance only. Do not enter patient information or use it for medical advice. See [SECURITY_CHATBOT.md](SECURITY_CHATBOT.md) before enabling it.

## Technology

- Python and Flask
- Jinja2, HTML, and CSS
- PostgreSQL with `psycopg2`
- Flask-WTF for CSRF protection
- Flask-Limiter for request limits
- OpenAI-compatible Python SDK for the optional Groq chatbot

## Project layout

```text
hospital_management/
├── app.py
├── chatbot_kb.py
├── setup_users.py
├── requirements.txt
├── database/
│   ├── SCHEMA_HMS.sql
│   ├── INSERTING_HMS.sql
│   ├── INDEX_HMS.sql
│   ├── VIEWS_HMS.sql
│   ├── TRIGGER_HMS.sql
│   ├── ONLINE_PATIENT_REGISTRATION.sql
│   └── TESTING_HMS.sql
├── static/
│   ├── style.css
│   └── *.svg
└── templates/
    ├── base.html
    └── ...
```

## Requirements

- Python 3.10 or later
- PostgreSQL database (local or hosted)
- A Groq API key only if you want to enable the chatbot

## Local setup

### 1. Create and activate a virtual environment

From the project directory, run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux, activate it with:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Create a local `.env` file in the project directory (it is ignored by Git) and set:

```env
DATABASE_URL=replace-with-your-postgresql-connection-url
FLASK_SECRET_KEY=replace-with-a-long-random-secret
FLASK_DEBUG=false
```

Replace the `DATABASE_URL` value with the connection URL from your PostgreSQL provider. For local development, set `FLASK_DEBUG=true` if you need Flask's debugger. Do not enable the debugger in a public deployment. Keep real credentials and keys out of source control.

### 4. Prepare the database

Create a PostgreSQL database, then review and execute `database/SCHEMA_HMS.sql` against it. The schema defines the tables and relationships used by the app, including users, patients, appointments, prescriptions, audit logs, and laboratory tests. **Important:** this script also contains sample-data statements, including a prescription insert that assumes patient, medical-record, and medicine IDs already exist. On a fresh empty database, review the script and remove or defer those sample inserts before running it; add development data only after the required records and tables exist.

Optional scripts:

- `INSERTING_HMS.sql` adds sample hospital data. Use it only in a development/test database; it contains example patient and clinical information.
- `INDEX_HMS.sql`, `VIEWS_HMS.sql`, and `TRIGGER_HMS.sql` provide database indexes, views, and triggers. Review each script and its dependencies before applying it.
- `ONLINE_PATIENT_REGISTRATION.sql` is for an existing database that needs the online patient-account table. The current schema already defines `users` and its patient relationship; do not run this script on a fresh database without reviewing its `CREATE TABLE IF NOT EXISTS` behavior and role constraints.
- `TESTING_HMS.sql` contains SQL for database testing.

The `setup_users.py` script creates or refreshes demo staff accounts. Run it only against a local/test database, and inspect its contents before use. Its credentials are for demonstration, not production.

### 5. Start the application

```bash
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000). A signed-in patient is directed to the patient portal; staff members see pages allowed for their role.

## Optional chatbot configuration

Set `GROQ_API_KEY` in the local `.env` or deployment environment, then restart the app:

```env
GROQ_API_KEY=your-groq-api-key
```

Without this key, the app still starts and the chatbot widget remains hidden. When enabled, the assistant is available only to admins and receptionists, and sends general workflow questions to Groq. Avoid patient data; the implementation rejects common email/phone patterns, but this detection cannot catch every kind of sensitive information. See [SECURITY_CHATBOT.md](SECURITY_CHATBOT.md) and [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) for security details and manual checks.

## Roles at a glance

| Role | Main access |
|---|---|
| Admin | Hospital modules, staff management, analytics, and audit logs |
| Receptionist | Patient registration, rooms, appointments, and billing |
| Doctor | Patient and doctor directories, appointments, medical records, and lab ordering |
| Pharmacist | Medicine inventory and prescription dispensing |
| Lab technician | Laboratory test results |
| Patient | Personal portal, doctor directory, and appointment requests |

Authorization is enforced by the Flask routes; interface navigation is not a substitute for server-side access control.

## Security and privacy

- Store database credentials, Flask secrets, and API keys in environment variables or an ignored local `.env` file.
- Use a unique, strong `FLASK_SECRET_KEY` outside local development.
- Do not use the sample SQL data or demo accounts with real patient information.
- Do not expose debug mode or development credentials in a public environment.
- The chatbot is not a clinical tool. Do not provide it with patient details.
- Review the deployment platform's privacy, logging, and secret-management requirements before using real data.

## Contributing and validation

There is no automated test suite currently included. Use [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) for manual chatbot checks, and verify database connectivity, role access, and each workflow in a non-production environment after making changes.
