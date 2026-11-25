import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

import app as hms_app
from blueprints import user_mgmt


class ActiveSessionsCursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return {"total": 1}

    def fetchall(self):
        return [{
            "user_session_id": 23,
            "user_id": 7,
            "username": "admin",
            "full_name": "Test Admin",
            "role": "admin",
            "ip_address": "127.0.0.1",
            "user_agent": "Test Browser",
            "created_at": datetime(2026, 1, 1),
            "last_seen_at": datetime(2026, 1, 2),
            "expires_at": datetime(2026, 2, 1),
            "branch_id": 3,
            "branch_name": "North",
            "session_token_hash": "another-session",
        }]


class ActiveSessionsTests(unittest.TestCase):
    def test_admin_session_page_renders_revoke_action_and_only_active_sessions(self):
        cursor = ActiveSessionsCursor()

        @contextmanager
        def fake_db_cursor():
            yield cursor

        with patch.dict(
            hms_app.app.config,
            {"TESTING": True, "WTF_CSRF_ENABLED": False},
        ), patch.object(user_mgmt, "db_cursor", fake_db_cursor):
            client = hms_app.app.test_client()
            with client.session_transaction() as browser_session:
                browser_session["user_id"] = 7
                browser_session["role"] = "admin"

            response = client.get("/admin/erp/sessions")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"North", response.data)
        self.assertIn(b"/admin/erp/sessions/23/revoke", response.data)
        self.assertIn("s.expires_at > CURRENT_TIMESTAMP", cursor.queries[0][0])
        self.assertIn("u.is_active = TRUE", cursor.queries[0][0])
        self.assertIn("LEFT JOIN branches", cursor.queries[1][0])
        self.assertEqual(cursor.queries[1][1], (50, 0))


if __name__ == "__main__":
    unittest.main()
