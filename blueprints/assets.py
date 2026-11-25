from datetime import date
from decimal import Decimal, InvalidOperation

import psycopg2
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from erp_common import active_branch, db_cursor, role_required


assets_bp = Blueprint("assets", __name__, url_prefix="/assets")


def _branch(cur):
    branch = active_branch(cur, session["user_id"], session.get("branch_id"))
    if branch:
        session["branch_id"] = branch["branch_id"]
        session["branch_name"] = branch["branch_name"]
    return branch


def _audit_context(cur):
    cur.execute(
        "SELECT set_config('hms.user_id', %s, TRUE), set_config('hms.username', %s, TRUE)",
        (str(session["user_id"]), session.get("username", "")),
    )


def _page():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


def _money(raw, label):
    try:
        value = Decimal(raw or "0")
    except (InvalidOperation, TypeError):
        raise ValueError(f"Enter a valid {label}.")
    if not value.is_finite() or value < 0 or value > Decimal("9999999999.99"):
        raise ValueError(f"{label.title()} must be a non-negative amount with up to two decimals.")
    try:
        excess_precision = value != value.quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"{label.title()} must be a valid monetary amount.")
    if excess_precision:
        raise ValueError(f"{label.title()} must be a non-negative amount with up to two decimals.")
    return value


@assets_bp.get("/")
@role_required("admin")
def index():
    page, per_page = _page(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        assets_page, categories, total, total_pages = [], [], 0, 1
        if branch:
            cur.execute("SELECT COUNT(*) AS total FROM assets WHERE branch_id = %s", (branch["branch_id"],))
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT a.asset_id, a.asset_tag, a.asset_name, a.purchase_date,
                          a.purchase_cost, a.salvage_value, a.useful_life_months,
                          a.accumulated_depreciation, a.status, c.category_name,
                          LEAST(
                              a.purchase_cost - a.salvage_value,
                              ROUND(
                                  (a.purchase_cost - a.salvage_value) *
                                  LEAST(
                                      GREATEST(
                                          (EXTRACT(YEAR FROM AGE(CURRENT_DATE, a.purchase_date)) * 12
                                           + EXTRACT(MONTH FROM AGE(CURRENT_DATE, a.purchase_date)))::INT,
                                          0
                                      ),
                                      a.useful_life_months
                                  ) / a.useful_life_months,
                                  2
                              )
                          ) AS straight_line_depreciation,
                          a.purchase_cost - LEAST(
                              a.purchase_cost - a.salvage_value,
                              ROUND(
                                  (a.purchase_cost - a.salvage_value) *
                                  LEAST(
                                      GREATEST(
                                          (EXTRACT(YEAR FROM AGE(CURRENT_DATE, a.purchase_date)) * 12
                                           + EXTRACT(MONTH FROM AGE(CURRENT_DATE, a.purchase_date)))::INT,
                                          0
                                      ),
                                      a.useful_life_months
                                  ) / a.useful_life_months,
                                  2
                              )
                          ) AS net_book_value
                   FROM assets a JOIN asset_categories c USING (asset_category_id)
                   WHERE a.branch_id = %s ORDER BY a.asset_name
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            assets_page = cur.fetchall()
            cur.execute("SELECT asset_category_id, category_name FROM asset_categories ORDER BY category_name LIMIT 500")
            categories = cur.fetchall()
    return render_template(
        "assets/index.html", branch=branch, assets=assets_page, categories=categories,
        page=page, total=total, total_pages=total_pages,
    )


@assets_bp.post("/categories")
@role_required("admin")
def create_category():
    name = request.form.get("category_name", "").strip()
    description = request.form.get("description", "").strip()
    try:
        months = int(request.form.get("default_useful_life_months") or 0) or None
    except ValueError:
        months = -1
    if not name or len(name) > 100 or len(description) > 1000 or (months is not None and not 1 <= months <= 1200):
        flash("Review the category name and useful life.", "error")
        return redirect(url_for("assets.index"))
    try:
        with db_cursor() as cur:
            _audit_context(cur)
            cur.execute(
                """INSERT INTO asset_categories
                       (category_name, description, default_useful_life_months)
                   VALUES (%s, %s, %s)""",
                (name, description or None, months),
            )
            cur.connection.commit()
        flash("Asset category created.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to create asset category")
        flash("Category could not be saved. Category names must be unique.", "error")
    return redirect(url_for("assets.index"))


@assets_bp.post("/")
@role_required("admin")
def create():
    tag = request.form.get("asset_tag", "").strip().upper()
    name = request.form.get("asset_name", "").strip()
    serial = request.form.get("serial_number", "").strip()
    try:
        category_id = int(request.form.get("asset_category_id", ""))
        purchase_date = date.fromisoformat(request.form.get("purchase_date", ""))
        cost = _money(request.form.get("purchase_cost"), "purchase cost")
        salvage = _money(request.form.get("salvage_value"), "salvage value")
        life = int(request.form.get("useful_life_months", ""))
    except (ValueError, InvalidOperation) as error:
        flash(str(error) or "Enter valid asset details.", "error")
        return redirect(url_for("assets.index"))
    if not tag or len(tag) > 60 or not name or len(name) > 150 or len(serial) > 100 or not 1 <= life <= 1200 or salvage > cost:
        flash("Review the asset tag, name, useful life, and salvage value.", "error")
        return redirect(url_for("assets.index"))
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                flash("Create a branch and select it before adding assets.", "error")
                return redirect(url_for("branches.index"))
            cur.execute("SELECT asset_category_id FROM asset_categories WHERE asset_category_id = %s", (category_id,))
            if not cur.fetchone():
                flash("Choose an existing asset category.", "error")
                return redirect(url_for("assets.index"))
            _audit_context(cur)
            cur.execute(
                """INSERT INTO assets
                       (branch_id, asset_category_id, asset_tag, asset_name,
                        serial_number, purchase_date, purchase_cost, salvage_value,
                        useful_life_months)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    branch["branch_id"], category_id, tag, name, serial or None,
                    purchase_date, cost, salvage, life,
                ),
            )
            cur.connection.commit()
        flash("Asset added to the register.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to create asset")
        flash("Asset could not be saved. Asset tags must be unique.", "error")
    return redirect(url_for("assets.index"))


@assets_bp.get("/maintenance")
@role_required("admin")
def maintenance():
    page, per_page = _page(), 50
    with db_cursor() as cur:
        branch = _branch(cur)
        assets_list, logs, total, total_pages = [], [], 0, 1
        if branch:
            cur.execute("SELECT COUNT(*) AS total FROM maintenance_logs WHERE branch_id = %s", (branch["branch_id"],))
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT asset_id, asset_tag, asset_name FROM assets
                   WHERE branch_id = %s AND status <> 'disposed'
                   ORDER BY asset_name LIMIT 500""",
                (branch["branch_id"],),
            )
            assets_list = cur.fetchall()
            cur.execute(
                """SELECT m.maintenance_log_id, m.maintenance_type, m.scheduled_date,
                          m.performed_on, m.status, m.cost, m.details, a.asset_tag, a.asset_name
                   FROM maintenance_logs m JOIN assets a USING (asset_id)
                   WHERE m.branch_id = %s ORDER BY m.scheduled_date DESC NULLS LAST,
                          m.maintenance_log_id DESC
                   LIMIT %s OFFSET %s""",
                (branch["branch_id"], per_page, (page - 1) * per_page),
            )
            logs = cur.fetchall()
    return render_template(
        "assets/maintenance.html", branch=branch, assets=assets_list, logs=logs,
        page=page, total=total, total_pages=total_pages,
    )


@assets_bp.post("/maintenance")
@role_required("admin")
def create_maintenance():
    try:
        asset_id = int(request.form.get("asset_id", ""))
        cost = _money(request.form.get("cost"), "maintenance cost")
        scheduled = date.fromisoformat(request.form["scheduled_date"]) if request.form.get("scheduled_date") else None
    except (ValueError, InvalidOperation) as error:
        flash(str(error) or "Enter valid maintenance details.", "error")
        return redirect(url_for("assets.maintenance"))
    kind = request.form.get("maintenance_type", "")
    details = request.form.get("details", "").strip()
    provider = request.form.get("service_provider", "").strip()
    if kind not in {"preventive", "corrective", "inspection", "other"} or len(details) > 2000 or len(provider) > 150:
        flash("Review the maintenance type, provider, and details.", "error")
        return redirect(url_for("assets.maintenance"))
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            cur.execute("SELECT asset_id FROM assets WHERE asset_id = %s AND branch_id = %s", (asset_id, branch["branch_id"] if branch else None))
            if not branch or not cur.fetchone():
                flash("Choose an asset in the active branch.", "error")
                return redirect(url_for("assets.maintenance"))
            _audit_context(cur)
            cur.execute(
                """INSERT INTO maintenance_logs
                       (branch_id, asset_id, maintenance_type, scheduled_date,
                        service_provider, cost, details)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (branch["branch_id"], asset_id, kind, scheduled, provider or None, cost, details or None),
            )
            cur.connection.commit()
        flash("Maintenance schedule recorded.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to create maintenance log")
        flash("Maintenance entry could not be saved.", "error")
    return redirect(url_for("assets.maintenance"))


@assets_bp.post("/maintenance/<int:log_id>/complete")
@role_required("admin")
def complete_maintenance(log_id):
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            _audit_context(cur)
            cur.execute(
                """UPDATE maintenance_logs SET status = 'completed', performed_on = CURRENT_DATE
                   WHERE maintenance_log_id = %s AND branch_id = %s
                     AND status IN ('scheduled', 'in_progress')""",
                (log_id, branch["branch_id"] if branch else None),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Scheduled maintenance log was not found in this branch.", "error")
                return redirect(url_for("assets.maintenance"))
            cur.connection.commit()
        flash("Maintenance marked complete.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to complete maintenance log")
        flash("Maintenance status could not be updated.", "error")
    return redirect(url_for("assets.maintenance"))


@assets_bp.get("/assignments")
@role_required("admin")
def assignments():
    with db_cursor() as cur:
        branch = _branch(cur)
        assets_list, staff_list, departments, rows = [], [], [], []
        if branch:
            cur.execute("SELECT asset_id, asset_tag, asset_name FROM assets WHERE branch_id = %s AND status = 'active' ORDER BY asset_name LIMIT 500", (branch["branch_id"],))
            assets_list = cur.fetchall()
            cur.execute("SELECT staff_id, first_name, last_name FROM staff WHERE branch_id = %s ORDER BY first_name LIMIT 500", (branch["branch_id"],))
            staff_list = cur.fetchall()
            cur.execute("SELECT dept_id, dept_name FROM departments ORDER BY dept_name LIMIT 500")
            departments = cur.fetchall()
            cur.execute(
                """SELECT aa.asset_assignment_id, aa.assigned_at, aa.returned_at,
                          aa.notes, a.asset_tag, a.asset_name,
                          COALESCE(s.first_name || ' ' || s.last_name, d.dept_name) AS assigned_to
                   FROM asset_assignments aa JOIN assets a USING (asset_id)
                   LEFT JOIN staff s USING (staff_id)
                   LEFT JOIN departments d USING (dept_id)
                   WHERE aa.branch_id = %s ORDER BY aa.assigned_at DESC LIMIT 50""",
                (branch["branch_id"],),
            )
            rows = cur.fetchall()
    return render_template("assets/assignments.html", branch=branch, assets=assets_list, staff=staff_list, departments=departments, assignments=rows)


@assets_bp.post("/assignments")
@role_required("admin")
def create_assignment():
    try:
        asset_id = int(request.form.get("asset_id", ""))
        staff_id = int(request.form["staff_id"]) if request.form.get("staff_id") else None
        dept_id = int(request.form["dept_id"]) if request.form.get("dept_id") else None
    except ValueError:
        flash("Choose valid asset and assignment targets.", "error")
        return redirect(url_for("assets.assignments"))
    if (staff_id is None) == (dept_id is None):
        flash("Choose exactly one staff member or department.", "error")
        return redirect(url_for("assets.assignments"))
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            if not branch:
                flash("Select an active branch first.", "error")
                return redirect(url_for("branches.index"))
            cur.execute("SELECT asset_id FROM assets WHERE asset_id = %s AND branch_id = %s", (asset_id, branch["branch_id"]))
            if not cur.fetchone():
                flash("Choose an asset in the active branch.", "error")
                return redirect(url_for("assets.assignments"))
            if staff_id:
                cur.execute("SELECT staff_id FROM staff WHERE staff_id = %s AND branch_id = %s", (staff_id, branch["branch_id"]))
            else:
                cur.execute("SELECT dept_id FROM departments WHERE dept_id = %s AND (branch_id = %s OR branch_id IS NULL)", (dept_id, branch["branch_id"]))
            if not cur.fetchone():
                flash("Choose an assignment target in the active branch.", "error")
                return redirect(url_for("assets.assignments"))
            _audit_context(cur)
            cur.execute(
                """INSERT INTO asset_assignments (branch_id, asset_id, staff_id, dept_id)
                   VALUES (%s, %s, %s, %s)""",
                (branch["branch_id"], asset_id, staff_id, dept_id),
            )
            cur.connection.commit()
        flash("Asset assignment recorded.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to assign asset")
        flash("Asset could not be assigned. It may already have an active assignment.", "error")
    return redirect(url_for("assets.assignments"))


@assets_bp.post("/assignments/<int:assignment_id>/return")
@role_required("admin")
def return_assignment(assignment_id):
    try:
        with db_cursor() as cur:
            branch = _branch(cur)
            _audit_context(cur)
            cur.execute(
                """UPDATE asset_assignments SET returned_at = CURRENT_TIMESTAMP
                   WHERE asset_assignment_id = %s AND branch_id = %s AND returned_at IS NULL""",
                (assignment_id, branch["branch_id"] if branch else None),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Active assignment was not found.", "error")
                return redirect(url_for("assets.assignments"))
            cur.connection.commit()
        flash("Asset returned to the register.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to return assigned asset")
        flash("Asset assignment could not be closed.", "error")
    return redirect(url_for("assets.assignments"))
