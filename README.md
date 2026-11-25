# Hospital Management System

A Flask and PostgreSQL web application for common hospital administration workflows. The app uses Jinja templates to render the interface on the server and provides separate access for staff and patients.

## Features

- Sign-in, patient self-registration, hashed passwords, and role-based access.
- Role-specific dashboards and navigation for administrators, doctors, receptionists, pharmacists, laboratory technicians, accountants, HR managers, procurement officers, branch managers, and patients.
- Patient and doctor directories, appointments, medical records, and prescriptions.
- Administrators can add doctor and staff records by selecting a department using its name and ID.
- Medicine inventory, pharmacy dispensing, laboratory tests, room admission/discharge, and billing.
- Administrator analytics and audit logs.
- Patient portal for viewing personal appointments, records, and bills. Patients can request appointments by selecting a doctor by name.
- ERP accounting: branch-scoped chart of accounts and balanced journal drafts/posting.
- HR and payroll: attendance, leave approvals, salary-component calculations, and payroll review workflows.
- Procurement: branch vendors, requisitions, purchase orders, goods receipts, and vendor invoice payments.
- Asset management: branch asset register, maintenance history, assignments, and straight-line depreciation estimates.
- ERP user administration: staff accounts, admin password resets, session revocation, and module read/write permissions.
- Reports: date-filtered branch dashboards, general P&L summaries, doctor activity and inventory-level exports to CSV.
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
├── erp_common.py
├── blueprints/
│   ├── assets.py
│   ├── branches.py
│   ├── finance.py
│   ├── hr.py
│   ├── procurement.py
│   ├── reports.py
│   └── user_mgmt.py
├── chatbot_kb.py
├── setup_users.py
├── requirements.txt
├── database/
│   ├── SCHEMA_HMS_ERP.sql
│   ├── INDEX_HMS_ERP.sql
│   ├── TRIGGER_HMS_ERP.sql
│   ├── INSERTING_HMS.sql
│   ├── VIEWS_HMS.sql
│   └── TESTING_HMS.sql
├── static/
│   ├── style.css
│   └── *.svg
└── templates/
    ├── base.html
    ├── branches/
    ├── finance/
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

For a new ERP test database, create an empty PostgreSQL database and run these scripts in order:

1. `database/SCHEMA_HMS_ERP.sql`
2. `database/INDEX_HMS_ERP.sql`
3. `database/TRIGGER_HMS_ERP.sql`

The ERP schema includes the existing hospital tables plus the new ERP tables and roles. Create a branch in the app, then grant branch access to each staff user who needs the branch-scoped finance workspace.

`SCHEMA_HMS_ERP.sql` is only for an empty database. If you have already run all three ERP scripts on Neon, do not run them again and do not run a migration script. Upgrading a separate database that still has only the legacy HMS schema is not covered yet; back it up and wait for a dedicated migration before applying ERP changes.

The deployed ERP schema predates the `users.is_active` column used by the user-management module. For an existing ERP database, review and apply `database/ERP_USER_MGMT_PATCH.sql` once before using ERP account deactivation or the updated demo-user script. Do not execute it from the application; take a database backup and review the SQL first.

Optional scripts:

- `INSERTING_HMS.sql` adds sample hospital data. Use it only in a development/test database; it contains example patient and clinical information.
- `VIEWS_HMS.sql` and `TESTING_HMS.sql` provide optional views and database testing queries. Review their table dependencies before applying them.

The `setup_users.py` script creates or refreshes demo staff accounts, including an accountant, HR manager, procurement officer, and branch manager. Run it only against a local/test database, and inspect its contents before use. Its credentials are for demonstration, not production.

### ERP workflow notes

- ERP pages and reports are scoped to a user's active branch. Use the branch-access screen to grant access before signing in as an ERP staff role.
- Payroll totals use base salary plus active salary components. Tax withholding is not automated; configure policy before using payroll for production.
- Scheduled reports are saved but are not delivered until a background worker is deployed. Self-service email password resets are not enabled because outbound email is not configured.
- The current data model does not attach billing to appointments or journal lines to departments, and it has no complete stock-movement ledger. Accordingly, doctor revenue attribution, department P&L, and inventory turnover are not presented as calculated facts. The reports page surfaces appointment counts, overall posted-ledger P&L, and current stock levels instead.
- CSV exports are available for the reports shown. PDF export is not included.
- Session revocation takes effect on the user's next request. The admin can also deactivate an account to revoke all its stored sessions.

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

Run the automated unit tests with `python -m unittest discover -s tests -v`. Use [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) for manual chatbot checks, and verify database connectivity, role access, and each workflow in a non-production environment after making changes.
