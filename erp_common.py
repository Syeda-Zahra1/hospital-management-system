from contextlib import contextmanager
from functools import wraps
import os

import psycopg2
from flask import current_app, flash, jsonify, redirect, request, session, url_for
from psycopg2.extras import RealDictCursor


@contextmanager
def db_cursor():
    """Yield a dictionary cursor and close its connection after the request."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield cur
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                if request.path == "/api/chat":
                    return jsonify(error="Authentication required."), 401
                flash("Please login first.", "error")
                return redirect(url_for("login"))
            if session.get("role") not in allowed_roles:
                if request.path == "/api/chat":
                    return jsonify(error="You are not authorized to use this service."), 403
                flash("⛔ Access Denied — You are not authorized.", "error")
                return redirect(url_for("index"))
            module = request.blueprint
            role = session.get("role")
            if module and module in {
                "finance", "hr", "procurement", "assets", "branches", "reports"
            } and role != "admin":
                action = "write" if request.method in {"POST", "PUT", "PATCH", "DELETE"} else "read"
                try:
                    with db_cursor() as cur:
                        cur.execute(
                            """SELECT COUNT(*) AS configured,
                                      COALESCE(BOOL_OR(is_allowed) FILTER (WHERE role = %s), FALSE) AS allowed
                               FROM role_permissions
                               WHERE module_name = %s AND action_name = %s""",
                            (role, module, action),
                        )
                        permission = cur.fetchone()
                except psycopg2.Error:
                    current_app.logger.exception(
                        "Unable to verify ERP module permission",
                        extra={"module": module, "action": action},
                    )
                    return "Access could not be verified. Please try again.", 503
                if permission["configured"] and not permission["allowed"]:
                    flash("Your role is not permitted to perform this action in that module.", "error")
                    return redirect(url_for("index"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def active_branch(cur, user_id, selected_branch_id=None):
    """Return a user's accessible active branch without widening branch scope."""
    if selected_branch_id is not None:
        cur.execute(
            """SELECT b.branch_id, b.branch_name
               FROM branches b
               JOIN user_branch_access uba ON uba.branch_id = b.branch_id
               WHERE uba.user_id = %s AND b.branch_id = %s AND b.is_active = TRUE""",
            (user_id, selected_branch_id),
        )
    else:
        cur.execute(
            """SELECT b.branch_id, b.branch_name
               FROM branches b
               JOIN user_branch_access uba ON uba.branch_id = b.branch_id
               WHERE uba.user_id = %s AND b.is_active = TRUE
               ORDER BY uba.is_default DESC, b.branch_name
               LIMIT 1""",
            (user_id,),
        )
    return cur.fetchone()


def current_session_hash():
    import hashlib

    token = session.get("erp_session_token")
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sync_session_branch(cur, branch_id):
    token_hash = current_session_hash()
    if token_hash:
        cur.execute(
            """UPDATE user_sessions SET branch_id = %s
               WHERE session_token_hash = %s AND user_id = %s AND revoked_at IS NULL""",
            (branch_id, token_hash, session.get("user_id")),
        )
