import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

import db
from main import app


class ControlPlaneApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        db.DATABASE_PATH = Path(self.tempdir.name) / "api-test.db"
        os.environ.update(
            {
                "BRELOCK_COMPANY_NAME": "Acme",
                "BRELOCK_COMPANY_SLUG": "acme",
                "BRELOCK_ADMIN_EMAIL": "admin@acme.test",
                "BRELOCK_ADMIN_PASSWORD": "strong-test-password",
                "BRELOCK_ENROLLMENT_TOKEN": "company-enrollment-secret",
            }
        )
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.tempdir.cleanup()

    def test_registration_discovery_assignment_and_policy_download(self):
        registration = self.client.post(
            "/api/client/register",
            json={
                "company_slug": "acme",
                "enrollment_token": "company-enrollment-secret",
                "laptop_id": "0123456789abcdef0123456789abcdef",
                "hostname": "MacBook-Kasia",
                "platform": "macOS 15",
                "app_version": "0.2.0",
            },
        )
        self.assertEqual(registration.status_code, 200)
        headers = {"Authorization": f"Bearer {registration.json()['device_token']}"}
        heartbeat = self.client.post(
            "/api/client/heartbeat",
            headers=headers,
            json={
                "observations": [
                    {
                        "brelock_id": "A1B2C3D4E5F6",
                        "display_name": "breLock-D4E5F6",
                        "rssi": -61,
                    }
                ]
            },
        )
        self.assertEqual(heartbeat.status_code, 204)

        login = self.client.post(
            "/api/admin/login",
            json={"email": "admin@acme.test", "password": "strong-test-password"},
        )
        self.assertEqual(login.status_code, 200)
        overview = self.client.get("/api/admin/overview").json()
        self.assertEqual(overview["brelocks"][0]["id"], "A1B2C3D4E5F6")
        assignment = self.client.post(
            "/api/admin/assign",
            json={
                "laptop_id": "0123456789abcdef0123456789abcdef",
                "brelock_id": "A1B2C3D4E5F6",
            },
        )
        self.assertEqual(assignment.status_code, 204)

        self.client.post(
            "/api/client/heartbeat",
            headers=headers,
            json={
                "observations": [
                    {
                        "brelock_id": "A1B2C3D4E5F6",
                        "display_name": "breLock-D4E5F6",
                        "rssi": -67,
                    }
                ]
            },
        )
        telemetry = self.client.get("/api/admin/overview").json()["telemetry"]
        self.assertEqual(telemetry["0123456789abcdef0123456789abcdef"][-1]["rssi"], -67)

        policy = self.client.get("/api/client/config", headers=headers)
        self.assertEqual(policy.status_code, 200)
        self.assertTrue(policy.json()["assigned"])
        self.assertEqual(policy.json()["brelock_id"], "A1B2C3D4E5F6")

    def test_admin_endpoints_require_login(self):
        response = self.client.get("/api/admin/overview")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
