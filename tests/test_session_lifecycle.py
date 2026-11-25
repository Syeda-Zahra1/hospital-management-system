import unittest
from contextlib import contextmanager
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app as hms_app


class LoginCursor:
    def __init__(self, user):
        self.user = user
        self.connection = self
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        if "SELECT b.branch_id" in self.executed[-1][0]:
            return None
        return self.user

    def close(self):
        pass

    def commit(self):
        pass


class SessionLifecycleTests(unittest.TestCase):
    def test_login_issues_a_persistent_cookie_matching_session_expiry(self):
        user = {
            "user_id": 41,
            "username": "demo",
            "full_name": "Demo User",
            "role": "admin",
            "password_hash": generate_password_hash("password123"),
            "is_active": True,
        }
        cursor = LoginCursor(user)
        connection = type(
            "Connection",
            (),
            {
                "cursor": lambda self, *args, **kwargs: cursor,
                "close": lambda self: None,
            },
        )()

        @contextmanager
        def fake_db_cursor():
            yield cursor

        with patch.dict(
            hms_app.app.config,
            {"TESTING": True, "WTF_CSRF_ENABLED": False},
        ), patch.object(hms_app, "get_db", return_value=connection), patch.object(
            hms_app, "db_cursor", fake_db_cursor
        ):
            client = hms_app.app.test_client()
            response = client.post(
                "/login",
                data={"username": "demo", "password": "password123"},
            )
            with client.session_transaction() as browser_session:
                self.assertTrue(browser_session.permanent)

        self.assertEqual(response.status_code, 302)
        self.assertIn("Expires=", response.headers["Set-Cookie"])
        self.assertTrue(
            any(
                "INTERVAL '30 days'" in query
                for query, _ in cursor.executed
            )
        )


if __name__ == "__main__":
    unittest.main()
