-- Automatically update inventory timestamp
-- Whenever an inventory record is updated, PostgreSQL refreshes last_updated.

CREATE OR REPLACE FUNCTION update_inventory_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.last_updated := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_inventory_timestamp
BEFORE UPDATE ON inventory
FOR EACH ROW
EXECUTE FUNCTION update_inventory_timestamp();

-- Validate appointment, room, and payment statuses
-- The trigger ensures that status values match the predefined choices
CREATE OR REPLACE FUNCTION validate_status_values()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'appointments' THEN
        IF NEW.status IS NULL OR NEW.status NOT IN (
            'Scheduled',
            'Completed',
            'Cancelled',
            'No-show'
        ) THEN
            RAISE EXCEPTION
                'Invalid appointment status: %',
                NEW.status;
        END IF;

    ELSIF TG_TABLE_NAME = 'rooms' THEN
        IF NEW.status IS NULL OR NEW.status NOT IN (
            'Available',
            'Occupied',
            'Maintenance'
        ) THEN
            RAISE EXCEPTION
                'Invalid room status: %',
                NEW.status;
        END IF;

    ELSIF TG_TABLE_NAME = 'billing' THEN
        IF NEW.payment_status IS NULL
           OR NEW.payment_status NOT IN (
               'Pending',
               'Paid',
               'Partially Paid',
               'Cancelled'
           ) THEN
            RAISE EXCEPTION
                'Invalid payment status: %',
                NEW.payment_status;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_appointment_status
BEFORE INSERT OR UPDATE ON appointments
FOR EACH ROW
EXECUTE FUNCTION validate_status_values();

CREATE TRIGGER trg_validate_room_status
BEFORE INSERT OR UPDATE ON rooms
FOR EACH ROW
EXECUTE FUNCTION validate_status_values();

CREATE TRIGGER trg_validate_billing_status
BEFORE INSERT OR UPDATE ON billing
FOR EACH ROW
EXECUTE FUNCTION validate_status_values();

-- Prevent negative inventory quantities
-- This trigger rejects inventory records with negative quantities or negative reorder levels.
CREATE OR REPLACE FUNCTION validate_inventory()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.quantity IS NULL OR NEW.quantity < 0 THEN
        RAISE EXCEPTION
            'Inventory quantity cannot be NULL or negative';
    END IF;

    IF NEW.reorder_level IS NULL
       OR NEW.reorder_level < 0 THEN
        RAISE EXCEPTION
            'Reorder level cannot be NULL or negative';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_inventory
BEFORE INSERT OR UPDATE ON inventory
FOR EACH ROW
EXECUTE FUNCTION validate_inventory();

-- ERP triggers and trigger functions. Run after SCHEMA_HMS_ERP.sql and INDEX_HMS_ERP.sql.

BEGIN;

-- Maintain updated_at consistently for tables that expose it.
CREATE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    table_record RECORD;
BEGIN
    FOR table_record IN
        SELECT DISTINCT table_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND column_name = 'updated_at'
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE UPDATE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
            'trg_' || table_record.table_name || '_updated_at',
            table_record.table_name
        );
    END LOOP;
END;
$$;

-- Validate allowed workflow statuses even if a future schema edit relaxes
-- a table's CHECK constraint.
CREATE FUNCTION validate_erp_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    status_value TEXT := to_jsonb(NEW)->>'status';
    allowed_values TEXT[];
BEGIN
    CASE TG_TABLE_NAME
        WHEN 'journal_entries' THEN
            allowed_values := ARRAY['draft', 'posted', 'void'];
        WHEN 'attendance' THEN
            allowed_values := ARRAY['present', 'absent', 'late', 'half_day', 'on_leave'];
        WHEN 'leave_requests' THEN
            allowed_values := ARRAY['draft', 'submitted', 'approved', 'rejected', 'cancelled'];
        WHEN 'payroll_runs' THEN
            allowed_values := ARRAY['draft', 'approved', 'paid', 'cancelled'];
        WHEN 'purchase_requisitions' THEN
            allowed_values := ARRAY['draft', 'submitted', 'approved', 'rejected', 'converted', 'cancelled'];
        WHEN 'purchase_orders' THEN
            allowed_values := ARRAY['draft', 'approved', 'sent', 'partially_received', 'received', 'cancelled'];
        WHEN 'grn' THEN
            allowed_values := ARRAY['draft', 'received', 'cancelled'];
        WHEN 'vendor_invoices' THEN
            allowed_values := ARRAY['received', 'approved', 'partially_paid', 'paid', 'void'];
        WHEN 'payments' THEN
            allowed_values := ARRAY['pending', 'posted', 'void', 'refunded'];
        WHEN 'assets' THEN
            allowed_values := ARRAY['active', 'in_maintenance', 'retired', 'disposed'];
        WHEN 'maintenance_logs' THEN
            allowed_values := ARRAY['scheduled', 'in_progress', 'completed', 'cancelled'];
        ELSE
            RAISE EXCEPTION 'No ERP status validation configured for table %', TG_TABLE_NAME;
    END CASE;

    IF status_value IS NULL OR NOT (status_value = ANY (allowed_values)) THEN
        RAISE EXCEPTION 'Invalid status "%" for table %', status_value, TG_TABLE_NAME
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_journal_entries_status
    BEFORE INSERT OR UPDATE OF status ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_attendance_status
    BEFORE INSERT OR UPDATE OF status ON attendance
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_leave_requests_status
    BEFORE INSERT OR UPDATE OF status ON leave_requests
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_payroll_runs_status
    BEFORE INSERT OR UPDATE OF status ON payroll_runs
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_purchase_requisitions_status
    BEFORE INSERT OR UPDATE OF status ON purchase_requisitions
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_purchase_orders_status
    BEFORE INSERT OR UPDATE OF status ON purchase_orders
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_grn_status
    BEFORE INSERT OR UPDATE OF status ON grn
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_vendor_invoices_status
    BEFORE INSERT OR UPDATE OF status ON vendor_invoices
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_payments_status
    BEFORE INSERT OR UPDATE OF status ON payments
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_assets_status
    BEFORE INSERT OR UPDATE OF status ON assets
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();
CREATE TRIGGER trg_maintenance_logs_status
    BEFORE INSERT OR UPDATE OF status ON maintenance_logs
    FOR EACH ROW EXECUTE FUNCTION validate_erp_status();

-- A journal entry cannot be posted unless it has at least two balanced lines.
CREATE FUNCTION assert_posted_journal_balanced()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry_id INT;
    entry_ids       INT[];
    entry_status    VARCHAR(20);
    line_count      BIGINT;
    debit_total     NUMERIC(14,2);
    credit_total    NUMERIC(14,2);
BEGIN
    IF TG_TABLE_NAME = 'journal_entries' THEN
        entry_ids := ARRAY[NEW.journal_entry_id];
    ELSIF TG_OP = 'DELETE' THEN
        entry_ids := ARRAY[OLD.journal_entry_id];
    ELSIF TG_OP = 'UPDATE' THEN
        entry_ids := ARRAY[OLD.journal_entry_id, NEW.journal_entry_id];
    ELSE
        entry_ids := ARRAY[NEW.journal_entry_id];
    END IF;

    FOREACH target_entry_id IN ARRAY entry_ids LOOP
        SELECT status INTO entry_status
        FROM journal_entries
        WHERE journal_entry_id = target_entry_id;

        IF entry_status = 'posted' THEN
            SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
            INTO line_count, debit_total, credit_total
            FROM journal_lines
            WHERE journal_entry_id = target_entry_id;

            IF line_count < 2 OR debit_total <= 0 OR debit_total <> credit_total THEN
                RAISE EXCEPTION 'Posted journal entry % must have at least two balanced lines',
                    target_entry_id USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    END LOOP;

    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER trg_journal_lines_balanced
    AFTER INSERT OR UPDATE OR DELETE ON journal_lines
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION assert_posted_journal_balanced();
CREATE CONSTRAINT TRIGGER trg_journal_entries_balanced
    AFTER INSERT OR UPDATE ON journal_entries
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION assert_posted_journal_balanced();

-- Audit changes to finance, payroll, procurement, and asset-purchase data.
CREATE FUNCTION audit_erp_financial_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    old_row         JSONB;
    new_row         JSONB;
    target_row      JSONB;
    actor_id        INT;
    actor_name      TEXT;
    target_id       TEXT;
    target_branch   INT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        new_row := to_jsonb(NEW);
        target_row := new_row;
    ELSIF TG_OP = 'UPDATE' THEN
        old_row := to_jsonb(OLD);
        new_row := to_jsonb(NEW);
        target_row := new_row;
    ELSE
        old_row := to_jsonb(OLD);
        target_row := old_row;
    END IF;

    actor_id := NULLIF(current_setting('hms.user_id', TRUE), '')::INT;
    actor_name := NULLIF(current_setting('hms.username', TRUE), '');
    target_id := target_row->>TG_ARGV[0];
    target_branch := NULLIF(target_row->>'branch_id', '')::INT;

    IF target_branch IS NULL THEN
        CASE TG_TABLE_NAME
            WHEN 'journal_lines' THEN
                SELECT branch_id INTO target_branch
                FROM journal_entries
                WHERE journal_entry_id = (target_row->>'journal_entry_id')::INT;
            WHEN 'purchase_requisition_lines' THEN
                SELECT branch_id INTO target_branch
                FROM purchase_requisitions
                WHERE requisition_id = (target_row->>'requisition_id')::INT;
            WHEN 'po_lines' THEN
                SELECT branch_id INTO target_branch
                FROM purchase_orders
                WHERE purchase_order_id = (target_row->>'purchase_order_id')::INT;
            WHEN 'grn_lines' THEN
                SELECT branch_id INTO target_branch
                FROM grn
                WHERE grn_id = (target_row->>'grn_id')::INT;
            ELSE
                NULL;
        END CASE;
    END IF;

    INSERT INTO audit_logs (
        user_id, username, action, table_name, record_id, branch_id,
        before_values, after_values
    ) VALUES (
        actor_id,
        actor_name,
        LEFT(TG_OP || ' ' || TG_TABLE_NAME, 255),
        TG_TABLE_NAME,
        target_id,
        target_branch,
        old_row,
        new_row
    );

    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_audit_billing
    AFTER INSERT OR UPDATE OR DELETE ON billing
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('bill_id');
CREATE TRIGGER trg_audit_chart_of_accounts
    AFTER INSERT OR UPDATE OR DELETE ON chart_of_accounts
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('account_id');
CREATE TRIGGER trg_audit_journal_entries
    AFTER INSERT OR UPDATE OR DELETE ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('journal_entry_id');
CREATE TRIGGER trg_audit_journal_lines
    AFTER INSERT OR UPDATE OR DELETE ON journal_lines
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('journal_line_id');
CREATE TRIGGER trg_audit_taxes
    AFTER INSERT OR UPDATE OR DELETE ON taxes
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('tax_id');
CREATE TRIGGER trg_audit_payments
    AFTER INSERT OR UPDATE OR DELETE ON payments
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('payment_id');
CREATE TRIGGER trg_audit_payroll_runs
    AFTER INSERT OR UPDATE OR DELETE ON payroll_runs
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('payroll_run_id');
CREATE TRIGGER trg_audit_salary_components
    AFTER INSERT OR UPDATE OR DELETE ON salary_components
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('salary_component_id');
CREATE TRIGGER trg_audit_payslips
    AFTER INSERT OR UPDATE OR DELETE ON payslips
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('payslip_id');
CREATE TRIGGER trg_audit_vendors
    AFTER INSERT OR UPDATE OR DELETE ON vendors
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('vendor_id');
CREATE TRIGGER trg_audit_purchase_requisitions
    AFTER INSERT OR UPDATE OR DELETE ON purchase_requisitions
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('requisition_id');
CREATE TRIGGER trg_audit_requisition_lines
    AFTER INSERT OR UPDATE OR DELETE ON purchase_requisition_lines
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('requisition_line_id');
CREATE TRIGGER trg_audit_purchase_orders
    AFTER INSERT OR UPDATE OR DELETE ON purchase_orders
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('purchase_order_id');
CREATE TRIGGER trg_audit_po_lines
    AFTER INSERT OR UPDATE OR DELETE ON po_lines
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('po_line_id');
CREATE TRIGGER trg_audit_grn
    AFTER INSERT OR UPDATE OR DELETE ON grn
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('grn_id');
CREATE TRIGGER trg_audit_grn_lines
    AFTER INSERT OR UPDATE OR DELETE ON grn_lines
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('grn_line_id');
CREATE TRIGGER trg_audit_vendor_invoices
    AFTER INSERT OR UPDATE OR DELETE ON vendor_invoices
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('vendor_invoice_id');
CREATE TRIGGER trg_audit_assets
    AFTER INSERT OR UPDATE OR DELETE ON assets
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('asset_id');
CREATE TRIGGER trg_audit_maintenance_logs
    AFTER INSERT OR UPDATE OR DELETE ON maintenance_logs
    FOR EACH ROW EXECUTE FUNCTION audit_erp_financial_change('maintenance_log_id');

COMMIT;
