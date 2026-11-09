# Hospital Management System (HMS)

## Project Overview

The **Hospital Management System (HMS)** is a web-based application developed to manage and organize different hospital operations through a centralized system.

The application is built using Python Flask, Jinja2, PostgreSQL, HTML, and CSS. It follows a **Server-Side Rendering (SSR)** architecture, where Flask handles application logic and database operations, while Jinja2 dynamically generates HTML pages.

The database is hosted on **Neon PostgreSQL**, and the application is designed for deployment through Vercel.

## Technologies Used

- **Python** – Backend programming language
- **Flask** – Web application framework
- **Jinja2** – Server-side template rendering
- **PostgreSQL** – Relational database management system
- **psycopg2** – PostgreSQL database connectivity
- **HTML5** – Frontend page structure
- **CSS3** – Styling and user interface
- **Neon** – Cloud PostgreSQL database hosting
- **Git & GitHub** – Version control and source code management
- **Vercel** – Application deployment platform

## System Modules

The project includes the following functional areas:

### 1. User Authentication and Authorization
- User login and registration
- Password hashing and verification
- Role-based access to system functionality

### 2. Patient Management
- Patient registration and information management
- Patient records
- Online patient registration support

### 3. Doctor Management
- Doctor information management
- Doctor-related hospital operations

### 4. Appointment Management
- Appointment records and management
- Appointment booking information

### 5. Medical Records
- Patient medical records
- Prescription management
- Medical history information

### 6. Pharmacy Management
- Medicine management
- Prescription-related pharmacy operations
- Medicine dispensing

### 7. Laboratory Management
- Laboratory test records
- Lab test management

### 8. Room Management
- Hospital room information
- Patient room assignment
- Room discharge management

### 9. Billing Management
- Patient billing and payment-related operations

### 10. Administration and Analytics
- Administrative dashboard
- Hospital data overview
- Patient registration analytics

## Database Design

The application uses **PostgreSQL** as its relational database.

The database is designed to organize hospital information and maintain relationships between different entities.

The SQL scripts included in the project are:

| SQL File | Purpose |
|---|---|
| `SCHEMA_HMS.sql` | Creates the database tables and relationships |
| `INSERTING_HMS.sql` | Inserts initial/sample records |
| `INDEX_HMS.sql` | Creates indexes to improve query performance |
| `VIEWS_HMS.sql` | Defines database views for reusable queries |
| `TRIGGER_HMS.sql` | Defines database triggers and functions |
| `ONLINE_PATIENT_REGISTRATION.sql` | Contains online patient registration database logic |
| `TESTING_HMS.sql` | Contains SQL statements for database testing |

### Database Features

- Relational database structure
- Primary and foreign key relationships
- Data integrity constraints
- Indexes for frequently accessed data
- Views for reusable database queries
- Triggers for automated database operations

## Project Architecture

The application uses a traditional Flask server-side rendering architecture.

**Application flow:**

1. The user interacts with a page through the browser.
2. Flask receives the HTTP request.
3. The application executes the required database query using psycopg2.
4. PostgreSQL returns the requested data.
5. Flask passes the data to a Jinja2 template.
6. Jinja2 renders the HTML page.
7. The browser displays the generated page.

This architecture does not require a separate frontend framework or REST API for the current server-rendered pages.

## Project Structure

```text
hospital_management/
│
├── app.py
├── setup_users.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── database/
│   ├── SCHEMA_HMS.sql
│   ├── INSERTING_HMS.sql
│   ├── INDEX_HMS.sql
│   ├── VIEWS_HMS.sql
│   ├── TRIGGER_HMS.sql
│   ├── ONLINE_PATIENT_REGISTRATION.sql
│   └── TESTING_HMS.sql
│
├── templates/
│   ├── base.html
│   ├── Login.html
│   ├── Register.html
│   └── ...
│
└── static/
    └── style.css
```

## Installation and Local Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/hospital-management-system.git
```

Move into the project directory:

```bash
cd hospital-management-system
```

### Step 2: Create a Virtual Environment

```bash
python -m venv venv
```

Activate the environment.

**Windows:**

```bash
venv\Scripts\activate
```

**Linux / macOS:**

```bash
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

The application requires the following environment variables:

```env
DATABASE_URL=your_neon_database_connection_string
FLASK_SECRET_KEY=your_secure_secret_key
```

- `DATABASE_URL` contains the Neon PostgreSQL connection string.
- `FLASK_SECRET_KEY` is used to secure Flask sessions.

Never commit actual database credentials or secret keys to GitHub.

For local development, these variables can be configured in your terminal or loaded from a local `.env` file using `python-dotenv`, if configured in the application.

### Step 5: Database Configuration

1. Create a PostgreSQL database using Neon.
2. Obtain the database connection string from the Neon dashboard.
3. Configure the `DATABASE_URL` environment variable.
4. Execute the required SQL scripts in Neon in their correct dependency order.

Recommended initial setup order:

1. `SCHEMA_HMS.sql`
2. `INSERTING_HMS.sql`
3. `INDEX_HMS.sql`
4. `VIEWS_HMS.sql`
5. `TRIGGER_HMS.sql`

Check the SQL dependencies and corrections before executing scripts on a fresh database.

### Step 6: Run the Application

```bash
python app.py
```

Open the following address in your browser:

```text
http://127.0.0.1:5000/
```

## Deployment

The project uses:

- **GitHub** for source code hosting.
- **Vercel** for Flask application deployment.
- **Neon** for cloud PostgreSQL database hosting.

Deployment environment variables:

```text
DATABASE_URL
FLASK_SECRET_KEY
```

The application should be tested after deployment to verify database connectivity, authentication, page rendering, and the different management modules.

## Version Control

Git is used to track project changes.

To upload updates:

```bash
git add .
git commit -m "Update Hospital Management System"
git push
```

## Security Notes

- Database credentials should be stored in environment variables.
- Passwords should be stored using secure hashing.
- Access to system modules should be controlled through authorization.
- Database queries should use parameterized statements.
- State-changing operations should use appropriate HTTP methods and CSRF protection.
- Real patient information should not be used for public demonstrations without appropriate security and privacy safeguards.

## Project Purpose

This project demonstrates the development of a database-driven Hospital Management System using Flask and PostgreSQL. It brings multiple hospital management operations together in one web-based application and demonstrates practical implementation of relational database concepts, server-side rendering, authentication, and database integration.

---

**Project:** Hospital Management System (HMS)  
**Backend:** Python Flask  
**Database:** PostgreSQL (Neon)  
**Frontend:** HTML, CSS, Jinja2  
**Deployment:** Vercel  
**Source Control:** GitHub
