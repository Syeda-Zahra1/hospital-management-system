-- ==========================================
-- INDEXES
-- ==========================================

CREATE INDEX idx_doctors_dept
ON doctors(dept_id);

CREATE INDEX idx_staff_dept
ON staff(dept_id);

CREATE INDEX idx_appointments_patient
ON appointments(patient_id);

CREATE INDEX idx_appointments_doctor
ON appointments(doctor_id);

CREATE INDEX idx_appointments_date
ON appointments(appointment_date);

CREATE INDEX idx_appointments_status_date
ON appointments(status, appointment_date);

CREATE INDEX idx_medical_records_patient
ON medical_records(patient_id);

CREATE INDEX idx_medical_records_doctor
ON medical_records(doctor_id);

CREATE INDEX idx_medical_records_date
ON medical_records(visit_date);

CREATE INDEX idx_inventory_medicine
ON inventory(medicine_id);

CREATE INDEX idx_inventory_quantity
ON inventory(quantity);

CREATE INDEX idx_billing_patient
ON billing(patient_id);

CREATE INDEX idx_billing_status_date
ON billing(payment_status, bill_date);

CREATE INDEX idx_medicines_expiry
ON medicines(expiry_date);


-- ERP indexes. Run after SCHEMA_HMS_ERP.sql on a new ERP database.

BEGIN;

-- ---------- 9. INDEXES ----------
CREATE INDEX idx_departments_branch ON departments(branch_id);
CREATE INDEX idx_doctors_branch ON doctors(branch_id);
CREATE INDEX idx_patients_branch ON patients(branch_id);
CREATE INDEX idx_rooms_branch ON rooms(branch_id);
CREATE INDEX idx_appointments_branch_date ON appointments(branch_id, appointment_date);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX idx_medical_records_patient ON medical_records(patient_id);
CREATE INDEX idx_inventory_branch_medicine ON inventory(branch_id, medicine_id);
CREATE INDEX idx_billing_branch_date ON billing(branch_id, bill_date);
CREATE INDEX idx_billing_patient ON billing(patient_id);
CREATE INDEX idx_staff_branch ON staff(branch_id);
CREATE INDEX idx_users_branch ON users(branch_id);
CREATE INDEX idx_prescriptions_record ON prescriptions(record_id);
CREATE INDEX idx_lab_tests_branch_date ON lab_tests(branch_id, test_date);
CREATE INDEX idx_audit_logs_user_timestamp ON audit_logs(user_id, "timestamp" DESC);
CREATE INDEX idx_audit_logs_branch_timestamp ON audit_logs(branch_id, "timestamp" DESC);

CREATE INDEX idx_accounts_type ON chart_of_accounts(account_type);
CREATE INDEX idx_accounts_branch ON chart_of_accounts(branch_id);
CREATE INDEX idx_accounts_parent ON chart_of_accounts(parent_account_id);
CREATE INDEX idx_journal_entries_branch_date ON journal_entries(branch_id, entry_date);
CREATE INDEX idx_journal_entries_status ON journal_entries(status);
CREATE INDEX idx_journal_entries_creator ON journal_entries(created_by);
CREATE INDEX idx_journal_lines_entry ON journal_lines(journal_entry_id);
CREATE INDEX idx_journal_lines_account ON journal_lines(account_id);
CREATE INDEX idx_taxes_branch_active ON taxes(branch_id, is_active);
CREATE INDEX idx_payments_branch_date ON payments(branch_id, payment_date);
CREATE INDEX idx_payments_bill ON payments(bill_id);
CREATE INDEX idx_payments_vendor_invoice ON payments(vendor_invoice_id);
CREATE INDEX idx_payments_journal_entry ON payments(journal_entry_id);
CREATE INDEX idx_payments_recorder ON payments(recorded_by);

CREATE INDEX idx_attendance_branch_date ON attendance(branch_id, attendance_date);
CREATE INDEX idx_attendance_staff_date ON attendance(staff_id, attendance_date);
CREATE INDEX idx_leave_requests_staff_status ON leave_requests(staff_id, status);
CREATE INDEX idx_leave_requests_branch_dates ON leave_requests(branch_id, start_date, end_date);
CREATE INDEX idx_leave_requests_approver ON leave_requests(approved_by);
CREATE INDEX idx_payroll_runs_branch_period ON payroll_runs(branch_id, period_start, period_end);
CREATE INDEX idx_payroll_runs_processor ON payroll_runs(processed_by);
CREATE INDEX idx_payroll_runs_approver ON payroll_runs(approved_by);
CREATE INDEX idx_salary_components_staff_active ON salary_components(staff_id, is_active);
CREATE INDEX idx_salary_components_branch_staff ON salary_components(branch_id, staff_id);
CREATE INDEX idx_payslips_staff ON payslips(staff_id);
CREATE INDEX idx_payslips_run ON payslips(payroll_run_id);
CREATE INDEX idx_payslips_branch ON payslips(branch_id);

CREATE INDEX idx_vendors_branch ON vendors(branch_id);
CREATE INDEX idx_requisitions_branch_status ON purchase_requisitions(branch_id, status);
CREATE INDEX idx_requisitions_requester ON purchase_requisitions(requested_by);
CREATE INDEX idx_requisition_lines_requisition ON purchase_requisition_lines(requisition_id);
CREATE INDEX idx_requisition_lines_medicine ON purchase_requisition_lines(medicine_id);
CREATE INDEX idx_requisition_lines_category ON purchase_requisition_lines(asset_category_id);
CREATE INDEX idx_purchase_orders_branch_date ON purchase_orders(branch_id, order_date);
CREATE INDEX idx_purchase_orders_vendor ON purchase_orders(vendor_id);
CREATE INDEX idx_purchase_orders_requisition ON purchase_orders(requisition_id);
CREATE INDEX idx_po_lines_order ON po_lines(purchase_order_id);
CREATE INDEX idx_po_lines_medicine ON po_lines(medicine_id);
CREATE INDEX idx_po_lines_category ON po_lines(asset_category_id);
CREATE INDEX idx_grn_branch_date ON grn(branch_id, received_date);
CREATE INDEX idx_grn_purchase_order ON grn(purchase_order_id);
CREATE INDEX idx_grn_lines_grn ON grn_lines(grn_id);
CREATE INDEX idx_grn_lines_po_line ON grn_lines(po_line_id);
CREATE INDEX idx_vendor_invoices_branch_due ON vendor_invoices(branch_id, due_date);
CREATE INDEX idx_vendor_invoices_vendor ON vendor_invoices(vendor_id);
CREATE INDEX idx_vendor_invoices_po ON vendor_invoices(purchase_order_id);

CREATE INDEX idx_assets_branch_category ON assets(branch_id, asset_category_id);
CREATE INDEX idx_assets_vendor_invoice ON assets(vendor_invoice_id);
CREATE INDEX idx_maintenance_asset_date ON maintenance_logs(asset_id, scheduled_date);
CREATE INDEX idx_maintenance_branch_status ON maintenance_logs(branch_id, status);
CREATE INDEX idx_asset_assignments_asset ON asset_assignments(asset_id);
CREATE INDEX idx_asset_assignments_branch ON asset_assignments(branch_id);
CREATE INDEX idx_asset_assignments_staff ON asset_assignments(staff_id);
CREATE INDEX idx_asset_assignments_department ON asset_assignments(dept_id);
CREATE UNIQUE INDEX uq_asset_assignments_active_asset
    ON asset_assignments(asset_id) WHERE returned_at IS NULL;

CREATE INDEX idx_user_branch_access_user ON user_branch_access(user_id);
CREATE INDEX idx_user_branch_access_branch ON user_branch_access(branch_id);
CREATE UNIQUE INDEX uq_user_branch_default
    ON user_branch_access(user_id) WHERE is_default;
CREATE INDEX idx_role_permissions_role ON role_permissions(role);
CREATE INDEX idx_user_sessions_user_active ON user_sessions(user_id, expires_at)
    WHERE revoked_at IS NULL;
CREATE INDEX idx_user_sessions_branch ON user_sessions(branch_id);
CREATE INDEX idx_password_reset_user_expiry ON password_reset_tokens(user_id, expires_at);
CREATE INDEX idx_report_schedules_due ON report_schedules(next_run_at)
    WHERE is_active;
CREATE INDEX idx_report_schedules_user ON report_schedules(user_id);
CREATE INDEX idx_report_schedules_branch ON report_schedules(branch_id);

COMMIT;
