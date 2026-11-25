-- ============================================================
-- HMS CARE ERP - consolidated schema for a NEW, empty database
-- Do not run this file over an existing installation. Use the
-- separate migration script for existing databases.
-- Then run INDEX_HMS_ERP.sql followed by TRIGGER_HMS_ERP.sql.
-- ============================================================

BEGIN;

-- ---------- 1. BRANCHES ----------
CREATE TABLE branches (
    branch_id       SERIAL PRIMARY KEY,
    branch_code     VARCHAR(30) NOT NULL UNIQUE,
    branch_name     VARCHAR(150) NOT NULL,
    address         TEXT,
    phone           VARCHAR(30),
    email           VARCHAR(150),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 2. EXISTING HMS TABLES ----------
CREATE TABLE departments (
    dept_id         SERIAL PRIMARY KEY,
    dept_name       VARCHAR(100) NOT NULL UNIQUE,
    location        VARCHAR(100),
    phone           VARCHAR(20),
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE doctors (
    doctor_id       SERIAL PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    specialization  VARCHAR(100),
    email           VARCHAR(100) UNIQUE,
    phone           VARCHAR(20),
    dept_id         INT REFERENCES departments(dept_id) ON DELETE SET NULL,
    hire_date       DATE DEFAULT CURRENT_DATE,
    salary          NUMERIC(12,2),
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (salary IS NULL OR salary >= 0)
);

CREATE TABLE patients (
    patient_id          SERIAL PRIMARY KEY,
    first_name          VARCHAR(50) NOT NULL,
    last_name           VARCHAR(50) NOT NULL,
    dob                 DATE,
    gender              VARCHAR(10),
    phone               VARCHAR(20),
    email               VARCHAR(100),
    address             TEXT,
    blood_group         VARCHAR(5),
    registration_date   DATE DEFAULT CURRENT_DATE,
    branch_id           INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rooms (
    room_id             SERIAL PRIMARY KEY,
    room_number         VARCHAR(10) UNIQUE NOT NULL,
    room_type           VARCHAR(50),
    charges_per_day     NUMERIC(12,2),
    status              VARCHAR(20) DEFAULT 'Available',
    current_patient_id  INT REFERENCES patients(patient_id) ON DELETE SET NULL,
    branch_id           INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (charges_per_day IS NULL OR charges_per_day >= 0)
);

CREATE TABLE appointments (
    appointment_id      SERIAL PRIMARY KEY,
    patient_id          INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id           INT REFERENCES doctors(doctor_id) ON DELETE CASCADE,
    appointment_date    TIMESTAMP NOT NULL,
    status              VARCHAR(20) DEFAULT 'Scheduled',
    reason              TEXT,
    booked_by           VARCHAR(20) DEFAULT 'Staff',
    branch_id           INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE medical_records (
    record_id       SERIAL PRIMARY KEY,
    patient_id      INT REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_id       INT REFERENCES doctors(doctor_id) ON DELETE SET NULL,
    diagnosis       TEXT,
    prescription    TEXT,
    visit_date      DATE DEFAULT CURRENT_DATE,
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE medicines (
    medicine_id     SERIAL PRIMARY KEY,
    medicine_name   VARCHAR(100) NOT NULL,
    manufacturer    VARCHAR(100),
    price           NUMERIC(12,2),
    expiry_date     DATE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (price IS NULL OR price >= 0)
);

CREATE TABLE inventory (
    inventory_id    SERIAL PRIMARY KEY,
    medicine_id     INT REFERENCES medicines(medicine_id) ON DELETE CASCADE,
    quantity        INT DEFAULT 0,
    reorder_level   INT DEFAULT 10,
    last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (quantity IS NULL OR quantity >= 0),
    CHECK (reorder_level IS NULL OR reorder_level >= 0)
);

CREATE TABLE taxes (
    tax_id          SERIAL PRIMARY KEY,
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    tax_code        VARCHAR(30) NOT NULL UNIQUE,
    tax_name        VARCHAR(100) NOT NULL,
    rate_percent    NUMERIC(7,4) NOT NULL CHECK (rate_percent >= 0 AND rate_percent <= 100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE billing (
    bill_id         SERIAL PRIMARY KEY,
    patient_id      INT REFERENCES patients(patient_id) ON DELETE RESTRICT,
    total_amount    NUMERIC(12,2),
    payment_status  VARCHAR(20) DEFAULT 'Pending',
    bill_date       DATE DEFAULT CURRENT_DATE,
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    tax_id          INT REFERENCES taxes(tax_id) ON DELETE RESTRICT,
    subtotal_amount NUMERIC(12,2),
    tax_amount      NUMERIC(12,2) NOT NULL DEFAULT 0,
    invoice_number  VARCHAR(50) UNIQUE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (total_amount IS NULL OR total_amount >= 0),
    CHECK (subtotal_amount IS NULL OR subtotal_amount >= 0),
    CHECK (tax_amount >= 0)
);

CREATE TABLE staff (
    staff_id            SERIAL PRIMARY KEY,
    first_name          VARCHAR(50),
    last_name           VARCHAR(50),
    role                VARCHAR(50),
    phone               VARCHAR(20),
    email               VARCHAR(100),
    dept_id             INT REFERENCES departments(dept_id) ON DELETE SET NULL,
    salary              NUMERIC(12,2),
    join_date           DATE,
    designation         VARCHAR(100),
    employment_type     VARCHAR(30) CHECK (
                            employment_type IS NULL OR employment_type IN
                            ('full_time', 'part_time', 'contract', 'temporary', 'intern')
                        ),
    branch_id           INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (salary IS NULL OR salary >= 0)
);

CREATE TABLE users (
    user_id         SERIAL PRIMARY KEY,
    username        VARCHAR(150) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       VARCHAR(150) NOT NULL,
    role            VARCHAR(30) NOT NULL
                    CHECK (role IN (
                        'admin', 'doctor', 'receptionist', 'pharmacist', 'labtech',
                        'patient', 'accountant', 'hr_manager',
                        'procurement_officer', 'branch_manager'
                    )),
    patient_id      INT UNIQUE REFERENCES patients(patient_id) ON DELETE CASCADE,
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((role = 'patient' AND patient_id IS NOT NULL) OR
           (role <> 'patient' AND patient_id IS NULL))
);

CREATE TABLE prescriptions (
    prescription_id SERIAL PRIMARY KEY,
    record_id       INT REFERENCES medical_records(record_id) ON DELETE CASCADE,
    medicine_id     INT REFERENCES medicines(medicine_id),
    dosage          VARCHAR(50),
    quantity        INT DEFAULT 1,
    status          VARCHAR(20) DEFAULT 'Pending',
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lab_tests (
    test_id         SERIAL PRIMARY KEY,
    patient_id      INT REFERENCES patients(patient_id),
    doctor_id       INT REFERENCES doctors(doctor_id),
    test_name       VARCHAR(100) NOT NULL,
    result          TEXT,
    status          VARCHAR(20) DEFAULT 'Pending',
    test_date       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    log_id          SERIAL PRIMARY KEY,
    user_id         INT,
    username        VARCHAR(150),
    action          VARCHAR(255),
    "timestamp"     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address      INET,
    user_agent      TEXT,
    table_name      VARCHAR(100),
    record_id       VARCHAR(100),
    branch_id       INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    before_values   JSONB,
    after_values    JSONB,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 3. FINANCE & ACCOUNTING ----------
CREATE TABLE chart_of_accounts (
    account_id          SERIAL PRIMARY KEY,
    branch_id           INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    account_code        VARCHAR(30) NOT NULL UNIQUE,
    account_name        VARCHAR(150) NOT NULL,
    account_type        VARCHAR(20) NOT NULL CHECK (
                            account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense')
                        ),
    normal_balance      VARCHAR(10) NOT NULL CHECK (normal_balance IN ('debit', 'credit')),
    parent_account_id   INT REFERENCES chart_of_accounts(account_id) ON DELETE RESTRICT,
    description         TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE journal_entries (
    journal_entry_id    SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    entry_number        VARCHAR(50) NOT NULL,
    entry_date          DATE NOT NULL,
    description         TEXT NOT NULL,
    source_type         VARCHAR(50),
    source_id           BIGINT,
    status              VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'posted', 'void')),
    created_by          INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (branch_id, entry_number)
);

CREATE TABLE journal_lines (
    journal_line_id     SERIAL PRIMARY KEY,
    journal_entry_id    INT NOT NULL REFERENCES journal_entries(journal_entry_id) ON DELETE RESTRICT,
    account_id          INT NOT NULL REFERENCES chart_of_accounts(account_id) ON DELETE RESTRICT,
    line_description    TEXT,
    debit               NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit              NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);

-- ---------- 4. HR & PAYROLL ----------
CREATE TABLE attendance (
    attendance_id       SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    staff_id            INT NOT NULL REFERENCES staff(staff_id) ON DELETE RESTRICT,
    attendance_date     DATE NOT NULL,
    check_in            TIMESTAMP,
    check_out           TIMESTAMP,
    status              VARCHAR(20) NOT NULL DEFAULT 'present'
                        CHECK (status IN ('present', 'absent', 'late', 'half_day', 'on_leave')),
    notes               TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (staff_id, attendance_date),
    CHECK (check_out IS NULL OR check_in IS NOT NULL),
    CHECK (check_out IS NULL OR check_out > check_in)
);

CREATE TABLE leave_requests (
    leave_request_id    SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    staff_id            INT NOT NULL REFERENCES staff(staff_id) ON DELETE RESTRICT,
    leave_type          VARCHAR(20) NOT NULL CHECK (leave_type IN ('annual', 'sick', 'casual')),
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    reason              TEXT,
    status              VARCHAR(20) NOT NULL DEFAULT 'submitted'
                        CHECK (status IN ('draft', 'submitted', 'approved', 'rejected', 'cancelled')),
    approved_by         INT REFERENCES users(user_id) ON DELETE RESTRICT,
    approved_at         TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_date >= start_date)
);

CREATE TABLE payroll_runs (
    payroll_run_id      SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'approved', 'paid', 'cancelled')),
    total_gross         NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_gross >= 0),
    total_deductions    NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_deductions >= 0),
    total_tax           NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_tax >= 0),
    total_net           NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_net >= 0),
    processed_by        INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    approved_by         INT REFERENCES users(user_id) ON DELETE RESTRICT,
    approved_at         TIMESTAMP,
    paid_at             TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (branch_id, period_start, period_end),
    CHECK (period_end >= period_start)
);

CREATE TABLE salary_components (
    salary_component_id SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    staff_id            INT NOT NULL REFERENCES staff(staff_id) ON DELETE RESTRICT,
    component_name      VARCHAR(100) NOT NULL,
    component_type      VARCHAR(20) NOT NULL CHECK (component_type IN ('earning', 'deduction')),
    amount              NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    is_taxable          BOOLEAN NOT NULL DEFAULT TRUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payslips (
    payslip_id          SERIAL PRIMARY KEY,
    payroll_run_id      INT NOT NULL REFERENCES payroll_runs(payroll_run_id) ON DELETE RESTRICT,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    staff_id            INT NOT NULL REFERENCES staff(staff_id) ON DELETE RESTRICT,
    basic_salary        NUMERIC(12,2) NOT NULL CHECK (basic_salary >= 0),
    gross_pay           NUMERIC(12,2) NOT NULL CHECK (gross_pay >= 0),
    deductions          NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (deductions >= 0),
    tax_amount          NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    net_pay             NUMERIC(12,2) NOT NULL CHECK (net_pay >= 0),
    component_details   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (payroll_run_id, staff_id)
);

-- ---------- 5. PROCUREMENT & SUPPLY CHAIN ----------
CREATE TABLE asset_categories (
    asset_category_id   SERIAL PRIMARY KEY,
    category_name       VARCHAR(100) NOT NULL UNIQUE,
    description         TEXT,
    default_useful_life_months INT CHECK (
                                default_useful_life_months IS NULL OR default_useful_life_months > 0
                            ),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vendors (
    vendor_id           SERIAL PRIMARY KEY,
    branch_id           INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    vendor_code         VARCHAR(40) NOT NULL UNIQUE,
    vendor_name         VARCHAR(150) NOT NULL,
    contact_name        VARCHAR(100),
    email               VARCHAR(150),
    phone               VARCHAR(30),
    address             TEXT,
    tax_number          VARCHAR(50),
    payment_terms_days  INT NOT NULL DEFAULT 30 CHECK (payment_terms_days >= 0),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE purchase_requisitions (
    requisition_id      SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    requisition_number  VARCHAR(50) NOT NULL,
    requested_by        INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    dept_id             INT REFERENCES departments(dept_id) ON DELETE RESTRICT,
    request_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    needed_by           DATE,
    justification       TEXT,
    status              VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'submitted', 'approved', 'rejected', 'converted', 'cancelled')),
    approved_by         INT REFERENCES users(user_id) ON DELETE RESTRICT,
    approved_at         TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (branch_id, requisition_number)
);

CREATE TABLE purchase_requisition_lines (
    requisition_line_id SERIAL PRIMARY KEY,
    requisition_id      INT NOT NULL REFERENCES purchase_requisitions(requisition_id) ON DELETE RESTRICT,
    item_description    VARCHAR(255) NOT NULL,
    medicine_id         INT REFERENCES medicines(medicine_id) ON DELETE RESTRICT,
    asset_category_id   INT REFERENCES asset_categories(asset_category_id) ON DELETE RESTRICT,
    quantity            NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    estimated_unit_cost NUMERIC(12,2) CHECK (
                            estimated_unit_cost IS NULL OR estimated_unit_cost >= 0
                        ),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE purchase_orders (
    purchase_order_id   SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    po_number           VARCHAR(50) NOT NULL,
    vendor_id           INT NOT NULL REFERENCES vendors(vendor_id) ON DELETE RESTRICT,
    requisition_id      INT REFERENCES purchase_requisitions(requisition_id) ON DELETE RESTRICT,
    order_date          DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_delivery_date DATE,
    status              VARCHAR(25) NOT NULL DEFAULT 'draft'
                        CHECK (status IN (
                            'draft', 'approved', 'sent', 'partially_received',
                            'received', 'cancelled'
                        )),
    subtotal_amount     NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (subtotal_amount >= 0),
    tax_amount          NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount        NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    created_by          INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (branch_id, po_number)
);

CREATE TABLE po_lines (
    po_line_id          SERIAL PRIMARY KEY,
    purchase_order_id   INT NOT NULL REFERENCES purchase_orders(purchase_order_id) ON DELETE RESTRICT,
    line_number         INT NOT NULL CHECK (line_number > 0),
    item_description    VARCHAR(255) NOT NULL,
    medicine_id         INT REFERENCES medicines(medicine_id) ON DELETE RESTRICT,
    asset_category_id   INT REFERENCES asset_categories(asset_category_id) ON DELETE RESTRICT,
    quantity            NUMERIC(12,3) NOT NULL CHECK (quantity > 0),
    unit_price          NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    tax_id              INT REFERENCES taxes(tax_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (purchase_order_id, line_number)
);

CREATE TABLE grn (
    grn_id              SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    grn_number          VARCHAR(50) NOT NULL,
    purchase_order_id   INT NOT NULL REFERENCES purchase_orders(purchase_order_id) ON DELETE RESTRICT,
    received_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    received_by         INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    status              VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'received', 'cancelled')),
    notes               TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (branch_id, grn_number)
);

CREATE TABLE grn_lines (
    grn_line_id         SERIAL PRIMARY KEY,
    grn_id              INT NOT NULL REFERENCES grn(grn_id) ON DELETE RESTRICT,
    po_line_id          INT NOT NULL REFERENCES po_lines(po_line_id) ON DELETE RESTRICT,
    quantity_received   NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (quantity_received >= 0),
    quantity_rejected   NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (quantity_rejected >= 0),
    notes               TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vendor_invoices (
    vendor_invoice_id   SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    vendor_id           INT NOT NULL REFERENCES vendors(vendor_id) ON DELETE RESTRICT,
    purchase_order_id   INT REFERENCES purchase_orders(purchase_order_id) ON DELETE RESTRICT,
    invoice_number      VARCHAR(80) NOT NULL,
    invoice_date        DATE NOT NULL,
    due_date            DATE,
    subtotal_amount     NUMERIC(12,2) NOT NULL CHECK (subtotal_amount >= 0),
    tax_amount          NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount        NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    status              VARCHAR(25) NOT NULL DEFAULT 'received'
                        CHECK (status IN ('received', 'approved', 'partially_paid', 'paid', 'void')),
    created_by          INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (vendor_id, invoice_number),
    CHECK (due_date IS NULL OR due_date >= invoice_date)
);

CREATE TABLE payments (
    payment_id          SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    payment_number      VARCHAR(50) NOT NULL,
    direction           VARCHAR(10) NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    bill_id             INT REFERENCES billing(bill_id) ON DELETE RESTRICT,
    vendor_invoice_id   INT REFERENCES vendor_invoices(vendor_invoice_id) ON DELETE RESTRICT,
    journal_entry_id    INT REFERENCES journal_entries(journal_entry_id) ON DELETE RESTRICT,
    amount              NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    payment_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    payment_method      VARCHAR(20) NOT NULL CHECK (
                            payment_method IN ('cash', 'bank_transfer', 'card', 'cheque', 'other')
                        ),
    reference_number    VARCHAR(100),
    status              VARCHAR(20) NOT NULL DEFAULT 'posted'
                        CHECK (status IN ('pending', 'posted', 'void', 'refunded')),
    recorded_by         INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (branch_id, payment_number),
    CHECK (
        (direction = 'incoming' AND bill_id IS NOT NULL AND vendor_invoice_id IS NULL) OR
        (direction = 'outgoing' AND vendor_invoice_id IS NOT NULL AND bill_id IS NULL)
    )
);

-- ---------- 6. ASSET MANAGEMENT ----------
CREATE TABLE assets (
    asset_id                SERIAL PRIMARY KEY,
    branch_id               INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    asset_category_id       INT NOT NULL REFERENCES asset_categories(asset_category_id) ON DELETE RESTRICT,
    asset_tag               VARCHAR(60) NOT NULL UNIQUE,
    asset_name              VARCHAR(150) NOT NULL,
    serial_number           VARCHAR(100),
    purchase_date           DATE NOT NULL,
    purchase_cost           NUMERIC(12,2) NOT NULL CHECK (purchase_cost >= 0),
    salvage_value           NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (salvage_value >= 0),
    useful_life_months      INT NOT NULL CHECK (useful_life_months > 0),
    accumulated_depreciation NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (accumulated_depreciation >= 0),
    depreciation_method     VARCHAR(20) NOT NULL DEFAULT 'straight_line'
                            CHECK (depreciation_method = 'straight_line'),
    vendor_invoice_id       INT REFERENCES vendor_invoices(vendor_invoice_id) ON DELETE RESTRICT,
    dept_id                 INT REFERENCES departments(dept_id) ON DELETE RESTRICT,
    status                  VARCHAR(20) NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'in_maintenance', 'retired', 'disposed')),
    notes                   TEXT,
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (salvage_value <= purchase_cost),
    CHECK (accumulated_depreciation <= purchase_cost - salvage_value)
);

CREATE TABLE maintenance_logs (
    maintenance_log_id  SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    asset_id            INT NOT NULL REFERENCES assets(asset_id) ON DELETE RESTRICT,
    maintenance_type    VARCHAR(30) NOT NULL
                        CHECK (maintenance_type IN ('preventive', 'corrective', 'inspection', 'other')),
    scheduled_date      DATE,
    performed_on        DATE,
    status              VARCHAR(20) NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
    service_provider    VARCHAR(150),
    cost                NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (cost >= 0),
    details             TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE asset_assignments (
    asset_assignment_id SERIAL PRIMARY KEY,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    asset_id            INT NOT NULL REFERENCES assets(asset_id) ON DELETE RESTRICT,
    staff_id            INT REFERENCES staff(staff_id) ON DELETE RESTRICT,
    dept_id             INT REFERENCES departments(dept_id) ON DELETE RESTRICT,
    assigned_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    returned_at         TIMESTAMP,
    notes               TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((staff_id IS NOT NULL AND dept_id IS NULL) OR
           (staff_id IS NULL AND dept_id IS NOT NULL)),
    CHECK (returned_at IS NULL OR returned_at >= assigned_at)
);

-- ---------- 7. BRANCH ACCESS & USER MANAGEMENT ----------
CREATE TABLE user_branch_access (
    user_branch_access_id SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    branch_id           INT NOT NULL REFERENCES branches(branch_id) ON DELETE RESTRICT,
    is_default          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, branch_id)
);

CREATE TABLE role_permissions (
    role_permission_id  SERIAL PRIMARY KEY,
    role                VARCHAR(30) NOT NULL CHECK (role IN (
                            'admin', 'doctor', 'receptionist', 'pharmacist', 'labtech',
                            'patient', 'accountant', 'hr_manager',
                            'procurement_officer', 'branch_manager'
                        )),
    module_name         VARCHAR(80) NOT NULL,
    action_name         VARCHAR(40) NOT NULL,
    is_allowed          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (role, module_name, action_name)
);

CREATE TABLE user_sessions (
    user_session_id    SERIAL PRIMARY KEY,
    user_id            INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    session_token_hash VARCHAR(64) NOT NULL UNIQUE,
    branch_id          INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    ip_address         INET,
    user_agent         TEXT,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at         TIMESTAMP NOT NULL,
    revoked_at         TIMESTAMP,
    updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (expires_at > created_at)
);

CREATE TABLE password_reset_tokens (
    password_reset_token_id SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    token_hash          VARCHAR(64) NOT NULL UNIQUE,
    expires_at          TIMESTAMP NOT NULL,
    used_at             TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- 8. REPORT SCHEDULING ----------
CREATE TABLE report_schedules (
    report_schedule_id SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    branch_id           INT REFERENCES branches(branch_id) ON DELETE RESTRICT,
    report_type         VARCHAR(80) NOT NULL,
    frequency           VARCHAR(20) NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly')),
    report_parameters  JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_run_at         TIMESTAMP,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMIT;
