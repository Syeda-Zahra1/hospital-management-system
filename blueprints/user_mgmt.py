import psycopg2
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from erp_common import current_session_hash, db_cursor, role_required


user_mgmt_bp = Blueprint("user_mgmt", __name__, url_prefix="/admin/erp")
ROLES = (
    "admin", "doctor", "receptionist", "pharmacist", "labtech",
    "accountant", "hr_manager", "procurement_officer", "branch_manager",
)
MODULES = ("finance", "hr", "procurement", "assets", "branches", "reports")
DEFAULT_ACCESS = {
    "admin": set(MODULES),
    "accountant": {"finance", "procurement", "reports"},
    "hr_manager": {"hr"},
    "procurement_officer": {"procurement"},
    "branch_manager": {"branches", "reports"},
}


def _seed_permissions(cur):
    for role in ROLES:
        for module in MODULES:
            for action in ("read", "write"):
                allowed = module in DEFAULT_ACCESS.get(role, set())
                cur.execute(
                    """INSERT INTO role_permissions (role, module_name, action_name, is_allowed)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (role, module_name, action_name) DO NOTHING""",
                    (role, module, action, allowed),
                )


def _page():
    try:
        return max(1, int(request.args.get("page", "1")))
    except ValueError:
        return 1


@user_mgmt_bp.get("/users")
@role_required("admin")
def users():
    page, per_page = _page(), 50
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM users WHERE role <> 'patient'")
        total = cur.fetchone()["total"]
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, total_pages)
        cur.execute(
            """SELECT u.user_id, u.username, u.full_name, u.role, u.is_active,
                      b.branch_name
               FROM users u
               LEFT JOIN user_branch_access uba
                 ON uba.user_id = u.user_id AND uba.is_default = TRUE
               LEFT JOIN branches b ON b.branch_id = uba.branch_id
               WHERE u.role <> 'patient'
               ORDER BY u.full_name, u.username LIMIT %s OFFSET %s""",
            (per_page, (page - 1) * per_page),
        )
        users_page = cur.fetchall()
        cur.execute(
            """SELECT branch_id, branch_name FROM branches
               WHERE is_active = TRUE ORDER BY branch_name LIMIT 500"""
        )
        branches = cur.fetchall()
    return render_template(
        "user_mgmt/users.html", users=users_page, branches=branches,
        roles=ROLES, page=page, total=total, total_pages=total_pages,
    )


@user_mgmt_bp.post("/users")
@role_required("admin")
def create_user():
    username = request.form.get("username", "").strip().lower()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "")
    try:
        branch_id = int(request.form["branch_id"]) if request.form.get("branch_id") else None
    except ValueError:
        branch_id = -1
    if (
        not username or len(username) > 150 or not full_name or len(full_name) > 150
        or role not in ROLES or len(password) < 8 or len(password) > 256 or branch_id == -1
    ):
        flash("Enter a username, full name, valid role, and password of at least 8 characters.", "error")
        return redirect(url_for("user_mgmt.users"))
    try:
        with db_cursor() as cur:
            if branch_id is not None:
                cur.execute(
                    "SELECT branch_id FROM branches WHERE branch_id = %s AND is_active = TRUE",
                    (branch_id,),
                )
                if not cur.fetchone():
                    flash("Choose an active branch.", "error")
                    return redirect(url_for("user_mgmt.users"))
            cur.execute(
                """INSERT INTO users (username, password_hash, full_name, role)
                   VALUES (%s, %s, %s, %s) RETURNING user_id""",
                (username, generate_password_hash(password), full_name, role),
            )
            user_id = cur.fetchone()["user_id"]
            if branch_id is not None:
                cur.execute(
                    """INSERT INTO user_branch_access (user_id, branch_id, is_default)
                       VALUES (%s, %s, TRUE)""",
                    (user_id, branch_id),
                )
            cur.execute(
                """INSERT INTO audit_logs
                       (user_id, username, action, branch_id, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s, %s::inet, %s)""",
                (
                    session["user_id"], session.get("username"),
                    f"Created {role} account {username}", branch_id,
                    request.remote_addr, request.headers.get("User-Agent", "")[:1000],
                ),
            )
            cur.connection.commit()
        flash("User account created.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to create ERP user")
        flash("User could not be created. Check that the username is unique.", "error")
    return redirect(url_for("user_mgmt.users"))


@user_mgmt_bp.post("/users/<int:user_id>/toggle")
@role_required("admin")
def toggle_user(user_id):
    try:
        with db_cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(42104212)")
            cur.execute(
                "SELECT user_id, username, role, is_active FROM users WHERE user_id = %s FOR UPDATE",
                (user_id,),
            )
            target = cur.fetchone()
            if not target or target["role"] == "patient":
                flash("Staff user was not found.", "error")
                return redirect(url_for("user_mgmt.users"))
            deactivate = target["is_active"]
            if deactivate and target["role"] == "admin":
                cur.execute(
                    "SELECT COUNT(*) AS active_admins FROM users WHERE role = 'admin' AND is_active = TRUE"
                )
                if cur.fetchone()["active_admins"] <= 1:
                    flash("The last active administrator cannot be deactivated.", "error")
                    return redirect(url_for("user_mgmt.users"))
            cur.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (not deactivate, user_id))
            if deactivate:
                cur.execute(
                    """UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP
                       WHERE user_id = %s AND revoked_at IS NULL""",
                    (user_id,),
                )
            cur.execute(
                """INSERT INTO audit_logs (user_id, username, action, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s::inet, %s)""",
                (
                    session["user_id"], session.get("username"),
                    f"{'Deactivated' if deactivate else 'Reactivated'} account {target['username']}",
                    request.remote_addr, request.headers.get("User-Agent", "")[:1000],
                ),
            )
            cur.connection.commit()
        flash("User account deactivated." if deactivate else "User account reactivated.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to change ERP user status")
        flash("User status could not be changed.", "error")
    return redirect(url_for("user_mgmt.users"))


@user_mgmt_bp.post("/users/<int:user_id>/role")
@role_required("admin")
def change_user_role(user_id):
    role = request.form.get("role", "")
    if role not in ROLES:
        flash("Choose a supported staff role.", "error")
        return redirect(url_for("user_mgmt.users"))
    try:
        with db_cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(42104212)")
            cur.execute(
                "SELECT username, role, is_active FROM users WHERE user_id = %s FOR UPDATE",
                (user_id,),
            )
            target = cur.fetchone()
            if not target or target["role"] == "patient":
                flash("Staff user was not found.", "error")
                return redirect(url_for("user_mgmt.users"))
            if target["role"] == "admin" and target["is_active"] and role != "admin":
                cur.execute(
                    "SELECT COUNT(*) AS active_admins FROM users WHERE role = 'admin' AND is_active = TRUE"
                )
                if cur.fetchone()["active_admins"] <= 1:
                    flash("The last active administrator cannot be changed to another role.", "error")
                    return redirect(url_for("user_mgmt.users"))
            cur.execute("UPDATE users SET role = %s WHERE user_id = %s", (role, user_id))
            cur.execute(
                """UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP
                   WHERE user_id = %s AND revoked_at IS NULL""",
                (user_id,),
            )
            cur.execute(
                """INSERT INTO audit_logs (user_id, username, action, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s::inet, %s)""",
                (
                    session["user_id"], session.get("username"),
                    f"Changed role for {target['username']} to {role}",
                    request.remote_addr, request.headers.get("User-Agent", "")[:1000],
                ),
            )
            cur.connection.commit()
        flash("User role updated. Their active sessions were revoked.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to change ERP user role")
        flash("User role could not be changed.", "error")
    return redirect(url_for("user_mgmt.users"))


@user_mgmt_bp.post("/users/<int:user_id>/password")
@role_required("admin")
def reset_password(user_id):
    password = request.form.get("password", "")
    if len(password) < 8 or len(password) > 256:
        flash("Password must contain 8 to 256 characters.", "error")
        return redirect(url_for("user_mgmt.users"))
    try:
        with db_cursor() as cur:
            cur.execute(
                """UPDATE users SET password_hash = %s
                   WHERE user_id = %s AND role <> 'patient'""",
                (generate_password_hash(password), user_id),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Staff user was not found.", "error")
                return redirect(url_for("user_mgmt.users"))
            cur.execute(
                """UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP
                   WHERE user_id = %s AND revoked_at IS NULL""",
                (user_id,),
            )
            cur.execute(
                """INSERT INTO audit_logs (user_id, username, action, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s::inet, %s)""",
                (
                    session["user_id"], session.get("username"),
                    f"Reset password for user ID {user_id}",
                    request.remote_addr, request.headers.get("User-Agent", "")[:1000],
                ),
            )
            cur.connection.commit()
        flash("Password reset. The user must sign in again.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to reset ERP user password")
        flash("Password could not be reset.", "error")
    return redirect(url_for("user_mgmt.users"))


@user_mgmt_bp.route("/permissions", methods=["GET", "POST"])
@role_required("admin")
def permissions():
    if request.method == "POST":
        try:
            with db_cursor() as cur:
                _seed_permissions(cur)
                for role in ROLES:
                    for module in MODULES:
                        for action in ("read", "write"):
                            allowed = request.form.get(f"{role}:{module}:{action}") == "on"
                            cur.execute(
                                """UPDATE role_permissions SET is_allowed = %s
                                   WHERE role = %s AND module_name = %s AND action_name = %s""",
                                (allowed, role, module, action),
                            )
                cur.connection.commit()
            flash("Role permissions updated.", "success")
        except psycopg2.Error:
            current_app.logger.exception("Unable to update ERP role permissions")
            flash("Role permissions could not be updated.", "error")
        return redirect(url_for("user_mgmt.permissions"))

    with db_cursor() as cur:
        _seed_permissions(cur)
        cur.connection.commit()
        cur.execute(
            """SELECT role, module_name, action_name, is_allowed
               FROM role_permissions
               WHERE module_name = ANY(%s) AND action_name IN ('read', 'write')""",
            (list(MODULES),),
        )
        rows = cur.fetchall()
    matrix = {
        (row["role"], row["module_name"], row["action_name"]): row["is_allowed"]
        for row in rows
    }
    return render_template(
        "user_mgmt/permissions.html", roles=ROLES, modules=MODULES, matrix=matrix,
    )


@user_mgmt_bp.get("/sessions")
@role_required("admin")
def sessions():
    page, per_page = _page(), 50
    with db_cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) AS total FROM user_sessions
               WHERE revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP"""
        )
        total = cur.fetchone()["total"]
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, total_pages)
        cur.execute(
            """SELECT s.user_session_id, s.user_id, u.username, u.full_name, u.role,
                      s.ip_address, s.user_agent, s.created_at, s.last_seen_at,
                      s.expires_at, s.branch_id, b.branch_name, s.session_token_hash
               FROM user_sessions s JOIN users u USING (user_id)
               LEFT JOIN branches b USING (branch_id)
               WHERE s.revoked_at IS NULL AND s.expires_at > CURRENT_TIMESTAMP
               ORDER BY s.last_seen_at DESC LIMIT %s OFFSET %s""",
            (per_page, (page - 1) * per_page),
        )
        session_rows = cur.fetchall()
    current_hash = current_session_hash()
    for row in session_rows:
        row["is_current"] = row["session_token_hash"] == current_hash
    return render_template(
        "user_mgmt/sessions.html", sessions=session_rows,
        page=page, total=total, total_pages=total_pages,
    )


@user_mgmt_bp.post("/sessions/<int:session_id>/revoke")
@role_required("admin")
def revoke_session(session_id):
    try:
        with db_cursor() as cur:
            cur.execute(
                """UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP
                   WHERE user_session_id = %s AND revoked_at IS NULL
                     AND session_token_hash <> %s""",
                (session_id, current_session_hash() or ""),
            )
            if cur.rowcount != 1:
                cur.connection.rollback()
                flash("Session was not found or is the current session.", "error")
                return redirect(url_for("user_mgmt.sessions"))
            cur.connection.commit()
        flash("Session revoked.", "success")
    except psycopg2.Error:
        current_app.logger.exception("Unable to revoke ERP session")
        flash("Session could not be revoked.", "error")
    return redirect(url_for("user_mgmt.sessions"))
