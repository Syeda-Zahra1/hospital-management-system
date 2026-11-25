import unittest

from setup_users import DEMO_USERS, demo_users_from_environment


class DemoUserConfigurationTests(unittest.TestCase):
    def test_demo_user_seeding_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ValueError, "disabled"):
            demo_users_from_environment({})

    def test_each_demo_account_requires_a_long_password(self):
        environment = {"HMS_ALLOW_DEMO_USERS": "true"}
        for _, password_key, _, _ in DEMO_USERS:
            environment[password_key] = "short"

        with self.assertRaisesRegex(ValueError, "at least 12 characters"):
            demo_users_from_environment(environment)

    def test_returns_demo_users_with_configured_passwords(self):
        environment = {"HMS_ALLOW_DEMO_USERS": "true"}
        for index, (_, password_key, _, _) in enumerate(DEMO_USERS):
            environment[password_key] = f"safe-demo-password-{index}"

        users = demo_users_from_environment(environment)

        self.assertEqual(len(users), len(DEMO_USERS))
        self.assertEqual(users[0][1], "safe-demo-password-0")


if __name__ == "__main__":
    unittest.main()
