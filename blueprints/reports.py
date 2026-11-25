import csv
from datetime import date
from io import StringIO

import psycopg2
from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, session, url_for

from erp_common import active_branch, db_cursor, role_required


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")
REPORT_ROLES = ("admin", "accountant", "branch_manager")


def _branch(cur):
    branch = active_branch(cur, session["user_id"], session.get("branch_id"))
    if branch:
        session["branch_id"] = branch["branch_id"]
        session["branch_name"] = branch["branch_name"]
    return branch


def _date_range():
    today = date.today()
    start_default = today.replace(day=1)
    try:
        start = date.fromisoformat(request.args.get("start_date", start_default.isoformat()))
        end = date.fromisoformat(request.args.get("end_date", today.isoformat()))
    except ValueError:
        raise ValueError("Choose valid start and end dates.")
    if end < start:
        raise ValueError("End date must be on or after start date.")
    if (end - start).days > 3660:
        raise ValueError("Date range cannot exceed 10 years.")
    return start, end


def _csv_text(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _report_data(cur, branch_id, start, end):
    cur.execute(
        """SELECT COUNT(*) AS patient_count
           FROM patients
           WHERE branch_id = %s AND registration_date BETWEEN %s AND %s""",
        (branch_id, start, end),
    )
    patient_count = cur.fetchone()["patient_count"]
    cur.execute(
        """SELECT COUNT(*) AS appointment_count,
                  COUNT(*) FILTER (WHERE status = 'Completed') AS completed_count
           FROM appointments
           WHERE branch_id = %s AND appointment_date::date BETWEEN %s AND %s""",
        (branch_id, start, end),
    )
    appointment_stats = cur.fetchone()
    cur.execute(
        """SELECT (
                      SELECT COALESCE(SUM(p.amount), 0)
                      FROM payments p
                      WHERE p.branch_id = %s AND p.direction = 'incoming'
                        AND p.status = 'posted' AND p.payment_date BETWEEN %s AND %s
                  ) AS collected,
                  COALESCE(SUM(
                      CASE WHEN b.payment_status = 'Paid' THEN 0
                           ELSE GREATEST(COALESCE(b.total_amount, 0) - COALESCE(paid.amount, 0), 0)
                      END
                  ), 0) AS outstanding
           FROM billing b
           LEFT JOIN (
               SELECT bill_id, SUM(amount) AS amount
               FROM payments
               WHERE branch_id = %s AND direction = 'incoming' AND status = 'posted'
               GROUP BY bill_id
           ) paid ON paid.bill_id = b.bill_id
           WHERE b.branch_id = %s AND b.bill_date BETWEEN %s AND %s
             AND b.payment_status IS DISTINCT FROM 'Cancelled'""",
        (branch_id, start, end, branch_id, branch_id, start, end),
    )
    revenue = cur.fetchone()
    cur.execute(
        """SELECT d.doctor_id, d.first_name || ' ' || d.last_name AS doctor_name,
                  COUNT(DISTINCT a.appointment_id) AS appointment_count,
                  COUNT(DISTINCT a.appointment_id) FILTER (WHERE a.status = 'Completed') AS completed_count,
                  NULL::numeric AS patient_billed
           FROM doctors d
           LEFT JOIN appointments a
             ON a.doctor_id = d.doctor_id AND a.branch_id = %s
            AND a.appointment_date::date BETWEEN %s AND %s
           WHERE d.branch_id = %s
           GROUP BY d.doctor_id
           ORDER BY appointment_count DESC, doctor_name
           LIMIT 500""",
        (branch_id, start, end, branch_id),
    )
    doctor_rows = cur.fetchall()
    cur.execute(
        """SELECT COALESCE(gender, 'Not specified') AS gender, COUNT(*) AS patient_count
           FROM patients
           WHERE branch_id = %s AND registration_date BETWEEN %s AND %s
           GROUP BY gender ORDER BY patient_count DESC""",
        (branch_id, start, end),
    )
    demographics = cur.fetchall()
    cur.execute(
        """SELECT a.account_type, COALESCE(SUM(l.debit), 0) AS debits,
                  COALESCE(SUM(l.credit), 0) AS credits
           FROM journal_entries e
           JOIN journal_lines l USING (journal_entry_id)
           JOIN chart_of_accounts a USING (account_id)
           WHERE e.branch_id = %s AND e.status = 'posted'
             AND e.entry_date BETWEEN %s AND %s
             AND a.account_type IN ('revenue', 'expense')
           GROUP BY a.account_type""",
        (branch_id, start, end),
    )
    pnl = {row["account_type"]: row for row in cur.fetchall()}
    cur.execute(
        """SELECT m.medicine_name, COALESCE(SUM(i.quantity), 0) AS on_hand,
                  COALESCE(SUM(i.reorder_level), 0) AS reorder_point
           FROM inventory i JOIN medicines m USING (medicine_id)
           WHERE i.branch_id = %s
           GROUP BY m.medicine_id, m.medicine_name
           ORDER BY m.medicine_name LIMIT 500""",
        (branch_id,),
    )
    inventory_rows = cur.fetchall()
    return {
        "patient_count": patient_count,
        "appointment_stats": appointment_stats,
        "revenue": revenue,
        "doctors": doctor_rows,
        "demographics": demographics,
        "pnl": pnl,
        "inventory": inventory_rows,
    }


@reports_bp.get("/")
@role_required(*REPORT_ROLES)
def dashboard():
    try:
        start, end = _date_range()
    except ValueError as error:
        flash(str(error), "error")
        start, end = date.today().replace(day=1), date.today()
    with db_cursor() as cur:
        branch = _branch(cur)
        reports = _report_data(cur, branch["branch_id"], start, end) if branch else None
        schedules = []
        if branch and session.get("role") == "admin":
            cur.execute(
                """SELECT report_schedule_id, report_type, frequency, next_run_at, is_active
                   FROM report_schedules WHERE branch_id = %s AND user_id = %s
                   ORDER BY created_at DESC LIMIT 50""",
                (branch["branch_id"], session["user_id"]),
            )
            schedules = cur.fetchall()
    return render_template(
        "reports/dashboard.html", branch=branch, reports=reports,
        start_date=start.isoformat(), end_date=end.isoformat(), schedules=schedules,
    )


@reports_bp.get("/export.csv")
@role_required(*REPORT_ROLES)
def export_csv():
    try:
        start, end = _date_range()
    except ValueError as error:
        return Response(str(error), status=400, mimetype="text/plain")
    report_type = request.args.get("type", "doctors")
    if report_type not in {"doctors", "demographics", "inventory", "profit-loss"}:
        return Response("Unknown report type.", status=400, mimetype="text/plain")
    with db_cursor() as cur:
        branch = _branch(cur)
        if not branch:
            return Response("Select an active branch first.", status=400, mimetype="text/plain")
        data = _report_data(cur, branch["branch_id"], start, end)

    output = StringIO()
    writer = csv.writer(output)
    if report_type == "doctors":
        writer.writerow(["Doctor", "Appointments", "Completed", "Revenue attribution"])
        for row in data["doctors"]:
            writer.writerow([_csv_text(row["doctor_name"]), row["appointment_count"], row["completed_count"], "Not linked in schema"])
    elif report_type == "demographics":
        writer.writerow(["Gender", "New registrations"])
        for row in data["demographics"]:
            writer.writerow([_csv_text(row["gender"]), row["patient_count"]])
    elif report_type == "inventory":
        writer.writerow(["Medicine", "On hand", "Reorder point"])
        for row in data["inventory"]:
            writer.writerow([_csv_text(row["medicine_name"]), row["on_hand"], row["reorder_point"]])
    else:
        writer.writerow(["Account type", "Debits", "Credits", "Net"])
        for account_type in ("revenue", "expense"):
            row = data["pnl"].get(account_type)
            debits = row["debits"] if row else 0
            credits = row["credits"] if row else 0
            net = credits - debits if account_type == "revenue" else debits - credits
            writer.writerow([account_type, debits, credits, net])

    response = Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = (
        f"attachment; filename=hms-{report_type}-{start.isoformat()}-{end.isoformat()}.csv"
    )
    return response


@reports_bp.post("/schedules")
@role_required("admin")
def create_schedule():
    report_type = request.form.get("report_type", "")
    frequency = request.form.get("frequency", "")
    if report_type not in {"doctors", "demographics", "inventory", "profit-loss"} or frequency not in {"daily", "weekly", "monthly"}:
        flash("Choose a supported report and schedule frequency.", "error")
        return redirect(url_for("reports.dashboard"))
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                flash("Select an active branch before scheduling reports.", "error")
                return redirect(url_for("reports.dashboard"))
            cur.execute(
                """INSERT INTO report_schedules
                       (user_id, branch_id, report_type, frequency, report_parameters, next_run_at)
                VALUES (
                    %s, %s, %s, %s, %s::jsonb,
                    CURRENT_TIMESTAMP + CASE %s
                        WHEN 'daily' THEN INTERVAL '1 day'
                        WHEN 'weekly' THEN INTERVAL '1 week'
                        ELSE INTERVAL '1 month'
                    END
                )""",
                (session["user_id"], branch["branch_id"], report_type, frequency, "{}", frequency),
            )
            cur.connection.commit()
        flash("Report schedule saved. Scheduled delivery requires a background worker.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to create report schedule")
        flash("Report schedule could not be saved.", "error")
    return redirect(url_for("reports.dashboard"))


@reports_bp.post("/schedules/<int:schedule_id>/toggle")
@role_required("admin")
def toggle_schedule(schedule_id):
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            cur.execute(
                """UPDATE report_schedules SET is_active = NOT is_active
                   WHERE report_schedule_id = %s AND branch_id = %s AND user_id = %s""",
                (schedule_id, branch["branch_id"] if branch else None, session["user_id"]),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Report schedule not found.", "error")
                return redirect(url_for("reports.dashboard"))
            cur.connection.commit()
        flash("Report schedule updated.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to update report schedule")
        flash("Report schedule could not be updated.", "error")
    return redirect(url_for("reports.dashboard"))
