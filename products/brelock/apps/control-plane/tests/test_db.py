import os
from pathlib import Path
import tempfile
import unittest

import db


class ControlPlaneDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        db.DATABASE_PATH = Path(self.tempdir.name) / "test.db"
        os.environ.update(
            {
                "BRELOCK_COMPANY_NAME": "Acme",
                "BRELOCK_COMPANY_SLUG": "acme",
                "BRELOCK_ADMIN_EMAIL": "admin@acme.test",
                "BRELOCK_ADMIN_PASSWORD": "strong-test-password",
                "BRELOCK_ENROLLMENT_TOKEN": "company-enrollment-secret",
            }
        )
        db.init_database()
        db.bootstrap_from_environment()

    def tearDown(self):
        self.tempdir.cleanup()

    def register(self, laptop_id="laptop-installation-0001"):
        token = db.register_laptop(
            "acme",
            "company-enrollment-secret",
            laptop_id,
            "MacBook-Kasia",
            "macOS 15",
            "0.2.0",
        )
        self.assertIsNotNone(token)
        return token, db.get_laptop_by_token(token)

    def test_admin_login_and_company_scope(self):
        result = db.create_admin_session("admin@acme.test", "strong-test-password")
        self.assertIsNotNone(result)
        token, _ = result
        admin = db.get_admin_by_session(token)
        self.assertEqual(admin["company_slug"], "acme")
        self.assertIsNone(db.create_admin_session("admin@acme.test", "bad-password"))

    def test_laptop_registration_requires_company_secret(self):
        token = db.register_laptop(
            "acme", "wrong-secret", "some-laptop-identifier", "Host", "macOS", "1"
        )
        self.assertIsNone(token)

    def test_complete_discovery_assignment_and_config_flow(self):
        _, laptop = self.register()
        db.heartbeat(
            laptop,
            [
                {
                    "brelock_id": "A1B2C3D4E5F6",
                    "display_name": "breLock-D4E5F6",
                    "rssi": -61,
                }
            ],
        )
        overview = db.admin_overview(laptop["company_id"])
        self.assertEqual(len(overview["laptops"]), 1)
        self.assertEqual(overview["brelocks"][0]["id"], "A1B2C3D4E5F6")

        db.assign_brelock(laptop["company_id"], laptop["id"], "A1B2C3D4E5F6")
        db.update_assignment(
            laptop["company_id"],
            laptop["id"],
            {
                "enabled": True,
                "rssi_threshold": -75,
                "reaction_seconds": 4,
                "reference_rssi": -60,
                "watchdog_seconds": 8,
            },
        )
        config = db.get_client_config(laptop)
        self.assertTrue(config["assigned"])
        self.assertEqual(config["brelock_id"], "A1B2C3D4E5F6")
        self.assertEqual(config["reaction_seconds"], 4)

    def test_one_brelock_cannot_be_assigned_to_two_laptops(self):
        _, laptop_one = self.register("laptop-installation-0001")
        _, laptop_two = self.register("laptop-installation-0002")
        db.add_brelock(laptop_one["company_id"], "112233445566", "Test")
        db.assign_brelock(laptop_one["company_id"], laptop_one["id"], "112233445566")
        with self.assertRaisesRegex(ValueError, "już przypisany"):
            db.assign_brelock(laptop_two["company_id"], laptop_two["id"], "112233445566")

    def test_identifiers_cannot_cross_company_boundaries(self):
        _, laptop = self.register("shared-laptop-identifier")
        db.add_brelock(laptop["company_id"], "112233445566", "Acme breLock")
        with db.connection() as conn:
            other_company_id = "other-company"
            conn.execute(
                "INSERT INTO companies VALUES (?, ?, ?, ?, ?)",
                (
                    other_company_id,
                    "Other Company",
                    "other",
                    db.token_hash("other-enrollment-token"),
                    db.now_iso(),
                ),
            )

        token = db.register_laptop(
            "other",
            "other-enrollment-token",
            "shared-laptop-identifier",
            "stolen-id",
            "Windows",
            "0.2.0",
        )
        self.assertIsNone(token)
        with self.assertRaisesRegex(ValueError, "innej firmie"):
            db.add_brelock(other_company_id, "112233445566", "stolen-brelock")


if __name__ == "__main__":
    unittest.main()
