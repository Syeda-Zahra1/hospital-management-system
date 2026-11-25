from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
import psycopg2

from erp_common import active_branch, db_cursor, role_required, sync_session_branch


branches_bp = Blueprint("branches", __name__, url_prefix="/branches")


def _page_number():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


@branches_bp.get("/")
@role_required("admin", "branch_manager")
def index():
    page = _page_number()
    per_page = 50
    with db_cursor() as cur:
        if session.get("role") == "admin":
            cur.execute("SELECT COUNT(*) AS total FROM branches")
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT b.branch_id, b.branch_code, b.branch_name, b.phone,
                          b.email, b.is_active
                   FROM branches b
                   ORDER BY b.branch_name
                   LIMIT %s OFFSET %s""",
                (per_page, (page - 1) * per_page),
            )
        else:
            cur.execute(
                """SELECT COUNT(*) AS total
                   FROM user_branch_access uba
                   JOIN branches b ON b.branch_id = uba.branch_id
                   WHERE uba.user_id = %s""",
                (session["user_id"],),
            )
            total = cur.fetchone()["total"]
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            cur.execute(
                """SELECT b.branch_id, b.branch_code, b.branch_name, b.phone,
                          b.email, b.is_active
                   FROM user_branch_access uba
                   JOIN branches b ON b.branch_id = uba.branch_id
                   WHERE uba.user_id = %s
                   ORDER BY b.branch_name
                   LIMIT %s OFFSET %s""",
                (session["user_id"], per_page, (page - 1) * per_page),
            )
        branches = cur.fetchall()
        if session.get("role") == "admin":
            cur.execute(
                """SELECT user_id, username, full_name, role
                   FROM users
                   WHERE role <> 'patient'
                   ORDER BY full_name
                   LIMIT 50"""
            )
            users = cur.fetchall()
            cur.execute(
                """SELECT branch_id, branch_name
                   FROM branches
                   WHERE is_active = TRUE
                   ORDER BY branch_name
                   LIMIT 500"""
            )
            access_branches = cur.fetchall()
        else:
            users = []
            access_branches = []
        current = active_branch(cur, session["user_id"], session.get("branch_id"))

    if current:
        session["branch_id"] = current["branch_id"]
        session["branch_name"] = current["branch_name"]

    return render_template(
        "branches/index.html",
        branches=branches,
        access_branches=access_branches,
        users=users,
        page=page,
        total_pages=total_pages,
        total=total,
        current_branch=current,
    )


@branches_bp.post("/")
@role_required("admin")
def create():
    branch_code = request.form.get("branch_code", "").strip().upper()
    branch_name = request.form.get("branch_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip().lower()
    address = request.form.get("address", "").strip()

    if not branch_code or len(branch_code) > 30 or not branch_name or len(branch_name) > 150:
        flash("Enter a branch code (up to 30 characters) and name (up to 150 characters).", "error")
        return redirect(url_for("branches.index"))
    if len(phone) > 30 or len(email) > 150:
        flash("Phone or email is longer than allowed.", "error")
        return redirect(url_for("branches.index"))

    try:
        with db_cursor() as cur:
            cur.execute(
                """INSERT INTO branches (branch_code, branch_name, phone, email, address)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING branch_id, branch_name""",
                (branch_code, branch_name, phone or None, email or None, address or None),
            )
            branch = cur.fetchone()
            cur.execute(
                """UPDATE user_branch_access
                   SET is_default = FALSE
                   WHERE user_id = %s AND is_default = TRUE""",
                (session["user_id"],),
            )
            cur.execute(
                """INSERT INTO user_branch_access (user_id, branch_id, is_default)
                   VALUES (%s, %s, TRUE)
                   ON CONFLICT (user_id, branch_id)
                   DO UPDATE SET is_default = TRUE""",
                (session["user_id"], branch["branch_id"]),
            )
            cur.execute(
                """INSERT INTO audit_logs
                       (user_id, username, action, branch_id, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s, %s::inet, %s)""",
                (
                    session["user_id"],
                    session.get("username"),
                    f"Created branch {branch['branch_name']}",
                    branch["branch_id"],
                    request.remote_addr,
                    request.headers.get("User-Agent", "")[:1000],
                ),
            )
            sync_session_branch(cur, branch["branch_id"])
            cur.connection.commit()
        session["branch_id"] = branch["branch_id"]
        session["branch_name"] = branch["branch_name"]
        flash("Branch created and selected.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to create ERP branch")
        flash("The branch could not be created. Check that its code is unique and try again.", "error")

    return redirect(url_for("branches.index"))


@branches_bp.post("/access")
@role_required("admin")
def grant_access():
    try:
        user_id = int(request.form.get("user_id", ""))
        branch_id = int(request.form.get("branch_id", ""))
    except ValueError:
        flash("Choose a valid user and branch.", "error")
        return redirect(url_for("branches.index"))

    make_default = request.form.get("is_default") == "on"
    try:
        with db_cursor() as cur:
            cur.execute(
                """SELECT user_id FROM users
                   WHERE user_id = %s AND role <> 'patient'""",
                (user_id,),
            )
            user = cur.fetchone()
            cur.execute(
                "SELECT branch_id FROM branches WHERE branch_id = %s AND is_active = TRUE",
                (branch_id,),
            )
            branch = cur.fetchone()
            if not user or not branch:
                flash("Choose an existing staff user and active branch.", "error")
                return redirect(url_for("branches.index"))

            if make_default:
                cur.execute(
                    """UPDATE user_branch_access SET is_default = FALSE
                       WHERE user_id = %s AND is_default = TRUE""",
                    (user_id,),
                )
            cur.execute(
                """INSERT INTO user_branch_access (user_id, branch_id, is_default)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, branch_id)
                   DO UPDATE SET is_default = EXCLUDED.is_default""",
                (user_id, branch_id, make_default),
            )
            cur.execute(
                """INSERT INTO audit_logs
                       (user_id, username, action, branch_id, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s, %s::inet, %s)""",
                (
                    session["user_id"],
                    session.get("username"),
                    f"Granted branch access to user ID {user_id}",
                    branch_id,
                    request.remote_addr,
                    request.headers.get("User-Agent", "")[:1000],
                ),
            )
            cur.connection.commit()
        flash("Branch access updated.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to grant ERP branch access")
        flash("Branch access could not be updated. Please try again.", "error")

    return redirect(url_for("branches.index"))


@branches_bp.post("/switch")
@role_required("admin", "branch_manager")
def switch():
    try:
        branch_id = int(request.form.get("branch_id", ""))
    except ValueError:
        flash("Choose a valid branch.", "error")
        return redirect(url_for("branches.index"))

    try:
        with db_cursor() as cur:
            branch = active_branch(cur, session["user_id"], branch_id)
            if branch:
                sync_session_branch(cur, branch["branch_id"])
                cur.connection.commit()
    except psycopg2.Error:
        current_app.logger.exception("Unable to switch ERP branch")
        flash("The branch could not be changed. Please try again.", "error")
        return redirect(url_for("branches.index"))

    if not branch:
        flash("You do not have access to that branch.", "error")
        return redirect(url_for("branches.index"))

    session["branch_id"] = branch["branch_id"]
    session["branch_name"] = branch["branch_name"]
    flash("Active branch changed.", "success")
    return redirect(url_for("branches.index"))
