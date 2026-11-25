from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation
import json

import psycopg2
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from erp_common import active_branch, db_cursor, role_required


hr_bp = Blueprint("hr", __name__, url_prefix="/hr")
HR_ROLES = ("admin", "hr_manager")


def _branch(cur):
    branch = active_branch(cur, session["user_id"], session.get("branch_id"))
    if branch:
        session["branch_id"] = branch["branch_id"]
        session["branch_name"] = branch["branch_name"]
    return branch


def _page():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


def _audit_context(cur):
    cur.execute(
        "SELECT set_config('hms.user_id', %s, TRUE), set_config('hms.username', %s, TRUE)",
        (str(session["user_id"]), session.get("username", "")),
    )


def _money(value, label):
    try:
        amount = Decimal(value or "0")
    except (InvalidOperation, TypeError):
        raise ValueError(f"Enter a valid {label}.")
    if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999.99"):
        raise ValueError(f"{label.title()} must be between 0 and 9,999,999,999.99.")
    try:
        excess_precision = amount != amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"{label.title()} must be a valid monetary amount.")
    if excess_precision:
        raise ValueError(f"{label.title()} can have up to two decimal places.")
    return amount


def _is_full_payroll_month(period_start, period_end):
    return (
        period_start.day == 1
        and period_end
        == date(
            period_start.year,
            period_start.month,
            monthrange(period_start.year, period_start.month)[1],
        )
    )


@hr_bp.get("/")
@role_required(*HR_ROLES)
def dashboard():
    with db_cursor() as cur:
        branch = _branch(cur)
        if not branch:
            stats = {"staff_count": 0, "present_today": 0, "pending_leave": 0, "latest_payroll": None}
        else:
            cur.execute("SELECT COUNT(*) AS total FROM staff WHERE branch_id = %s", (branch["branch_id"],))
            staff_count = cur.fetchone()["total"]
            cur.execute(
                """SELECT COUNT(*) AS total FROM attendance
                   WHERE branch_id = %s AND attendance_date = CURRENT_DATE AND status = 'present'""",
                (branch["branch_id"],),
            )
            present_today = cur.fetchone()["total"]
            cur.execute(
                """SELECT COUNT(*) AS total FROM leave_requests
                   WHERE branch_id = %s AND status = 'submitted'""",
                (branch["branch_id"],),
            )
            pending_leave = cur.fetchone()["total"]
            cur.execute(
                """SELECT period_start, period_end, status, total_net
                   FROM payroll_runs WHERE branch_id = %s
                   ORDER BY period_start DESC LIMIT 1""",
                (branch["branch_id"],),
            )
            latest_payroll = cur.fetchone()
            stats = {
                "staff_count": staff_count,
                "present_today": present_today,
                "pending_leave": pending_leave,
                "latest_payroll": latest_payroll,
            }
    return render_template("hr/dashboard.html", branch=branch, stats=stats)


@hr_bp.route("/employees", methods=["GET", "POST"])
@role_required(*HR_ROLES)
def employees():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        designation = request.form.get("designation", "").strip()
        employee_role = request.form.get("role", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        employment_type = request.form.get("employment_type", "")
        try:
            salary = _money(request.form.get("salary"), "salary") if request.form.get("salary") else None
            join_date = date.fromisoformat(request.form["join_date"]) if request.form.get("join_date") else None
            dept_id = int(request.form["dept_id"]) if request.form.get("dept_id") else None
        except (ValueError, InvalidOperation) as error:
            flash(str(error) or "Enter valid employee details.", "error")
            return redirect(url_for("hr.employees"))
        if (
            not first_name or len(first_name) > 50 or not last_name or len(last_name) > 50
            or len(designation) > 100 or len(employee_role) > 50
            or len(email) > 100 or len(phone) > 20
            or employment_type not in {"full_time", "part_time", "contract", "temporary", "intern"}
        ):
            flash("Review the employee name, contact details, designation and employment type.", "error")
            return redirect(url_for("hr.employees"))
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Create a branch and assign HR access before adding employees.", "error")
                    return redirect(url_for("hr.dashboard"))
                if dept_id:
                    cur.execute(
                        """SELECT dept_id FROM departments
                           WHERE dept_id = %s AND (branch_id = %s OR branch_id IS NULL)""",
                        (dept_id, branch["branch_id"]),
                    )
                    if not cur.fetchone():
                        flash("Choose a department in the active branch.", "error")
                        return redirect(url_for("hr.employees"))
                _audit_context(cur)
                cur.execute(
                    """INSERT INTO staff
                           (first_name, last_name, role, phone, email, dept_id, salary,
                            join_date, designation, employment_type, branch_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        first_name, last_name, employee_role or None, phone or None,
                        email or None, dept_id, salary, join_date,
                        designation or None, employment_type, branch["branch_id"],
                    ),
                )
                cur.connection.commit()
            flash("Employee record added.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create HR employee record")
            flash("Employee record could not be saved.", "error")
        return redirect(url_for("hr.employees"))

    page, per_page = _page(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        employees_page, departments, total, total_pages = [], [], 0, 1
        if branch:
            cur.execute(
                "SELECT dept_id, dept_name FROM departments WHERE branch_id = %s OR branch_id IS NULL ORDER BY dept_name LIMIT 500",
                (branch["branch_id"],),
            )
            departments = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS total FROM staff WHERE branch_id = %s", (branch["branch_id"],))
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT s.staff_id, s.first_name, s.last_name, s.role, s.email, s.phone,
                          s.salary, s.join_date, s.designation, s.employment_type,
                          d.dept_name
                   FROM staff s LEFT JOIN departments d ON d.dept_id = s.dept_id
                   WHERE s.branch_id = %s ORDER BY s.first_name, s.last_name
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            employees_page = cur.fetchall()
    return render_template(
        "hr/employees.html", branch=branch, employees=employees_page,
        departments=departments, page=page, total=total, total_pages=total_pages,
    )


@hr_bp.route("/attendance", methods=["GET", "POST"])
@role_required(*HR_ROLES)
def attendance():
    if request.method == "POST":
        try:
            staff_id = int(request.form.get("staff_id", ""))
            attendance_date = date.fromisoformat(request.form.get("attendance_date", ""))
            status = request.form.get("status", "")
        except ValueError:
            flash("Choose an employee and a valid attendance date.", "error")
            return redirect(url_for("hr.attendance"))
        if status not in {"present", "absent", "late", "half_day", "on_leave"}:
            flash("Choose a valid attendance status.", "error")
            return redirect(url_for("hr.attendance"))
        check_in = request.form.get("check_in") or None
        check_out = request.form.get("check_out") or None
        if check_out and not check_in:
            flash("A check-out time requires a check-in time.", "error")
            return redirect(url_for("hr.attendance"))

        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Create a branch and assign HR access first.", "error")
                    return redirect(url_for("hr.dashboard"))
                cur.execute(
                    "SELECT staff_id FROM staff WHERE staff_id = %s AND branch_id = %s",
                    (staff_id, branch["branch_id"]),
                )
                if not cur.fetchone():
                    flash("That employee is not in the active branch.", "error")
                    return redirect(url_for("hr.attendance"))
                _audit_context(cur)
                cur.execute(
                    """INSERT INTO attendance
                           (branch_id, staff_id, attendance_date, check_in, check_out, status)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (staff_id, attendance_date)
                       DO UPDATE SET check_in = EXCLUDED.check_in,
                                     check_out = EXCLUDED.check_out,
                                     status = EXCLUDED.status,
                                     branch_id = EXCLUDED.branch_id""",
                    (branch["branch_id"], staff_id, attendance_date, check_in, check_out, status),
                )
                cur.connection.commit()
            flash("Attendance saved.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to save HR attendance")
            flash("Attendance could not be saved. Check the employee and time values.", "error")
        return redirect(url_for("hr.attendance"))

    page, per_page = _page(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        employees = []
        rows = []
        total, total_pages = 0, 1
        if branch:
            cur.execute(
                """SELECT staff_id, first_name, last_name FROM staff
                   WHERE branch_id = %s ORDER BY first_name, last_name LIMIT 500""",
                (branch["branch_id"],),
            )
            employees = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS total FROM attendance WHERE branch_id = %s", (branch["branch_id"],))
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT a.attendance_date, a.check_in, a.check_out, a.status,
                          s.staff_id, s.first_name, s.last_name
                   FROM attendance a JOIN staff s ON s.staff_id = a.staff_id
                   WHERE a.branch_id = %s
                   ORDER BY a.attendance_date DESC, s.first_name
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            rows = cur.fetchall()
    return render_template(
        "hr/attendance.html", branch=branch, employees=employees,
        attendance_rows=rows, page=page, total=total, total_pages=total_pages,
        today=date.today().isoformat(),
    )


@hr_bp.route("/leave", methods=["GET", "POST"])
@role_required(*HR_ROLES)
def leave():
    if request.method == "POST":
        try:
            staff_id = int(request.form.get("staff_id", ""))
            start_date = date.fromisoformat(request.form.get("start_date", ""))
            end_date = date.fromisoformat(request.form.get("end_date", ""))
        except ValueError:
            flash("Choose an employee and valid leave dates.", "error")
            return redirect(url_for("hr.leave"))
        leave_type = request.form.get("leave_type", "")
        reason = request.form.get("reason", "").strip()
        if leave_type not in {"annual", "sick", "casual"} or end_date < start_date or len(reason) > 1000:
            flash("Review the leave type, dates, and reason.", "error")
            return redirect(url_for("hr.leave"))
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                cur.execute(
                    "SELECT staff_id FROM staff WHERE staff_id = %s AND branch_id = %s",
                    (staff_id, branch["branch_id"] if branch else None),
                )
                if not branch or not cur.fetchone():
                    flash("Select an employee from the active branch.", "error")
                    return redirect(url_for("hr.leave"))
                _audit_context(cur)
                cur.execute(
                    """INSERT INTO leave_requests
                           (branch_id, staff_id, leave_type, start_date, end_date, reason)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (branch["branch_id"], staff_id, leave_type, start_date, end_date, reason or None),
                )
                cur.connection.commit()
            flash("Leave request submitted for approval.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to submit HR leave request")
            flash("The leave request could not be saved.", "error")
        return redirect(url_for("hr.leave"))

    page, per_page = _page(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        requests_page, employees, total, total_pages = [], [], 0, 1
        if branch:
            cur.execute(
                """SELECT staff_id, first_name, last_name FROM staff
                   WHERE branch_id = %s ORDER BY first_name, last_name LIMIT 500""",
                (branch["branch_id"],),
            )
            employees = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS total FROM leave_requests WHERE branch_id = %s", (branch["branch_id"],))
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT l.leave_request_id, l.leave_type, l.start_date, l.end_date,
                          l.reason, l.status, s.first_name, s.last_name
                   FROM leave_requests l JOIN staff s ON s.staff_id = l.staff_id
                   WHERE l.branch_id = %s ORDER BY l.created_at DESC
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            requests_page = cur.fetchall()
    return render_template(
        "hr/leave.html", branch=branch, employees=employees, leave_requests=requests_page,
        page=page, total=total, total_pages=total_pages,
    )


@hr_bp.post("/leave/<int:leave_id>/<action>")
@role_required(*HR_ROLES)
def update_leave(leave_id, action):
    if action not in {"approve", "reject"}:
        flash("Invalid leave action.", "error")
        return redirect(url_for("hr.leave"))
    new_status = "approved" if action == "approve" else "rejected"
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                flash("Create a branch and assign HR access first.", "error")
                return redirect(url_for("hr.dashboard"))
            _audit_context(cur)
            cur.execute(
                """UPDATE leave_requests
                   SET status = %s, approved_by = %s, approved_at = CURRENT_TIMESTAMP
                   WHERE leave_request_id = %s AND branch_id = %s AND status = 'submitted'""",
                (new_status, session["user_id"], leave_id, branch["branch_id"]),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Pending leave request not found in the active branch.", "error")
                return redirect(url_for("hr.leave"))
            cur.connection.commit()
        flash(f"Leave request {new_status}.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to update HR leave request")
        flash("The leave request could not be updated.", "error")
    return redirect(url_for("hr.leave"))


@hr_bp.route("/salary-components", methods=["GET", "POST"])
@role_required(*HR_ROLES)
def salary_components():
    if request.method == "POST":
        try:
            staff_id = int(request.form.get("staff_id", ""))
            amount = _money(request.form.get("amount"), "salary component")
        except (ValueError, InvalidOperation) as error:
            flash(str(error) or "Enter a valid employee and amount.", "error")
            return redirect(url_for("hr.salary_components"))
        name = request.form.get("component_name", "").strip()
        component_type = request.form.get("component_type", "")
        is_taxable = request.form.get("is_taxable") == "on"
        if not name or len(name) > 100 or component_type not in {"earning", "deduction"}:
            flash("Enter a component name and choose earning or deduction.", "error")
            return redirect(url_for("hr.salary_components"))
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                cur.execute(
                    "SELECT staff_id FROM staff WHERE staff_id = %s AND branch_id = %s",
                    (staff_id, branch["branch_id"] if branch else None),
                )
                if not branch or not cur.fetchone():
                    flash("Choose an employee from the active branch.", "error")
                    return redirect(url_for("hr.salary_components"))
                _audit_context(cur)
                cur.execute(
                    """INSERT INTO salary_components
                           (branch_id, staff_id, component_name, component_type, amount, is_taxable)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (branch["branch_id"], staff_id, name, component_type, amount, is_taxable),
                )
                cur.connection.commit()
            flash("Salary component added.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create salary component")
            flash("Salary component could not be saved.", "error")
        return redirect(url_for("hr.salary_components"))

    page, per_page = _page(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        components, employees, total, total_pages = [], [], 0, 1
        if branch:
            cur.execute(
                """SELECT staff_id, first_name, last_name FROM staff
                   WHERE branch_id = %s ORDER BY first_name, last_name LIMIT 500""",
                (branch["branch_id"],),
            )
            employees = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*) AS total FROM salary_components WHERE branch_id = %s",
                (branch["branch_id"],),
            )
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT c.salary_component_id, c.component_name, c.component_type,
                          c.amount, c.is_taxable, c.is_active, s.first_name, s.last_name
                   FROM salary_components c JOIN staff s USING (staff_id)
                   WHERE c.branch_id = %s ORDER BY s.first_name, c.component_name
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            components = cur.fetchall()
    return render_template(
        "hr/salary_components.html", branch=branch, employees=employees,
        components=components, page=page, total=total, total_pages=total_pages,
    )


@hr_bp.post("/salary-components/<int:component_id>/toggle")
@role_required(*HR_ROLES)
def toggle_salary_component(component_id):
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            cur.execute(
                """UPDATE salary_components SET is_active = NOT is_active
                   WHERE salary_component_id = %s AND branch_id = %s""",
                (component_id, branch["branch_id"] if branch else None),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Salary component was not found in the active branch.", "error")
                return redirect(url_for("hr.salary_components"))
            cur.connection.commit()
        flash("Salary component status updated.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to update salary component")
        flash("Salary component status could not be updated.", "error")
    return redirect(url_for("hr.salary_components"))


@hr_bp.route("/payroll", methods=["GET", "POST"])
@role_required(*HR_ROLES)
def payroll():
    if request.method == "POST":
        try:
            period_start = date.fromisoformat(request.form.get("period_start", ""))
            period_end = date.fromisoformat(request.form.get("period_end", ""))
        except ValueError:
            flash("Choose valid payroll dates.", "error")
            return redirect(url_for("hr.payroll"))
        if not _is_full_payroll_month(period_start, period_end):
            flash("Payroll periods must cover one full calendar month.", "error")
            return redirect(url_for("hr.payroll"))
        try:
            with db_cursor() as cur:
                branch = _branch(cur)
                if not branch:
                    flash("Create a branch and assign HR access first.", "error")
                    return redirect(url_for("hr.dashboard"))
                cur.execute(
                    """SELECT staff_id, salary FROM staff
                       WHERE branch_id = %s AND salary IS NOT NULL AND salary > 0
                       ORDER BY staff_id""",
                    (branch["branch_id"],),
                )
                employees = cur.fetchall()
                if not employees:
                    flash("No salaried employees were found in this branch.", "error")
                    return redirect(url_for("hr.payroll"))
                cur.execute(
                    "SELECT set_config('hms.user_id', %s, TRUE), set_config('hms.username', %s, TRUE)",
                    (str(session["user_id"]), session.get("username", "")),
                )
                cur.execute(
                    """INSERT INTO payroll_runs
                           (branch_id, period_start, period_end, processed_by)
                       VALUES (%s, %s, %s, %s)
                       RETURNING payroll_run_id""",
                    (branch["branch_id"], period_start, period_end, session["user_id"]),
                )
                run_id = cur.fetchone()["payroll_run_id"]
                total_gross = Decimal("0")
                total_deductions = Decimal("0")
                total_net = Decimal("0")
                for employee in employees:
                    basic = Decimal(employee["salary"])
                    cur.execute(
                        """SELECT component_name, component_type, amount, is_taxable
                           FROM salary_components
                           WHERE staff_id = %s AND branch_id = %s AND is_active = TRUE
                           ORDER BY component_name""",
                        (employee["staff_id"], branch["branch_id"]),
                    )
                    component_rows = cur.fetchall()
                    earnings = sum(
                        (Decimal(row["amount"]) for row in component_rows if row["component_type"] == "earning"),
                        Decimal("0"),
                    )
                    deductions = sum(
                        (Decimal(row["amount"]) for row in component_rows if row["component_type"] == "deduction"),
                        Decimal("0"),
                    )
                    gross = basic + earnings
                    net = gross - deductions
                    if net < 0:
                        raise ValueError("An employee's deductions exceed their gross pay.")
                    details = [
                        {
                            "name": row["component_name"],
                            "type": row["component_type"],
                            "amount": str(row["amount"]),
                            "taxable": row["is_taxable"],
                        }
                        for row in component_rows
                    ]
                    details.append({"note": "Payroll tax is not calculated automatically; configure an approved tax component."})
                    cur.execute(
                        """INSERT INTO payslips
                               (payroll_run_id, branch_id, staff_id, basic_salary,
                                gross_pay, deductions, tax_amount, net_pay,
                                component_details)
                           VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s::jsonb)""",
                        (
                            run_id, branch["branch_id"], employee["staff_id"], basic,
                            gross, deductions, net,
                            json.dumps(details),
                        ),
                    )
                    total_gross += gross
                    total_deductions += deductions
                    total_net += net
                cur.execute(
                    """UPDATE payroll_runs
                       SET total_gross = %s, total_deductions = %s,
                           total_tax = 0, total_net = %s
                       WHERE payroll_run_id = %s""",
                    (total_gross, total_deductions, total_net, run_id),
                )
                cur.connection.commit()
            flash("Payroll run created as a draft. Verify payslips before approval.", "success")
        except ValueError as error:
            current_app.logger.warning("Payroll run validation failed: %s", error)
            flash(str(error), "error")
        except psycopg2.Error:
            current_app.logger.exception("Unable to create HR payroll run")
            flash("Payroll could not be processed. No partial payroll changes were committed.", "error")
        return redirect(url_for("hr.payroll"))

    page, per_page = _page(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        runs, total, total_pages = [], 0, 1
        if branch:
            cur.execute("SELECT COUNT(*) AS total FROM payroll_runs WHERE branch_id = %s", (branch["branch_id"],))
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT r.payroll_run_id, r.period_start, r.period_end, r.status,
                          r.total_gross, r.total_deductions, r.total_tax, r.total_net,
                          COUNT(p.payslip_id) AS payslip_count
                   FROM payroll_runs r LEFT JOIN payslips p ON p.payroll_run_id = r.payroll_run_id
                   WHERE r.branch_id = %s
                   GROUP BY r.payroll_run_id
                   ORDER BY r.period_start DESC
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            runs = cur.fetchall()
    return render_template("hr/payroll.html", branch=branch, payroll_runs=runs, page=page, total=total, total_pages=total_pages)


@hr_bp.get("/payroll/<int:run_id>")
@role_required(*HR_ROLES)
def payslips(run_id):
    with db_cursor() as cur:
        branch = _branch(cur)
        run = None
        payslip_rows = []
        if branch:
            cur.execute(
                """SELECT payroll_run_id, period_start, period_end, status
                   FROM payroll_runs
                   WHERE payroll_run_id = %s AND branch_id = %s""",
                (run_id, branch["branch_id"]),
            )
            run = cur.fetchone()
            if run:
                cur.execute(
                    """SELECT p.basic_salary, p.gross_pay, p.deductions, p.tax_amount,
                              p.net_pay, p.component_details, s.first_name, s.last_name
                       FROM payslips p JOIN staff s USING (staff_id)
                       WHERE p.payroll_run_id = %s AND p.branch_id = %s
                       ORDER BY s.first_name, s.last_name LIMIT 500""",
                    (run_id, branch["branch_id"]),
                )
                payslip_rows = cur.fetchall()
    if not run:
        flash("Payroll run was not found in the active branch.", "error")
        return redirect(url_for("hr.payroll"))
    return render_template("hr/payslips.html", branch=branch, run=run, payslips=payslip_rows)


@hr_bp.post("/payroll/<int:run_id>/<action>")
@role_required(*HR_ROLES)
def update_payroll(run_id, action):
    transitions = {"approve": ("draft", "approved"), "mark-paid": ("approved", "paid")}
    if action not in transitions:
        flash("Invalid payroll action.", "error")
        return redirect(url_for("hr.payroll"))
    expected, new_status = transitions[action]
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                flash("Create a branch and assign HR access first.", "error")
                return redirect(url_for("hr.dashboard"))
            cur.execute(
                """UPDATE payroll_runs
                   SET status = %s,
                       approved_by = CASE WHEN %s = 'approved' THEN %s ELSE approved_by END,
                       approved_at = CASE WHEN %s = 'approved' THEN CURRENT_TIMESTAMP ELSE approved_at END,
                       paid_at = CASE WHEN %s = 'paid' THEN CURRENT_TIMESTAMP ELSE paid_at END
                   WHERE payroll_run_id = %s AND branch_id = %s AND status = %s""",
                (
                    new_status, new_status, session["user_id"], new_status,
                    new_status, run_id, branch["branch_id"], expected,
                ),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Payroll run not found or is in the wrong status.", "error")
                return redirect(url_for("hr.payroll"))
            cur.connection.commit()
        flash(f"Payroll run marked {new_status}.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to update payroll run")
        flash("Payroll status could not be updated.", "error")
    return redirect(url_for("hr.payroll"))
