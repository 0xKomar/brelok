from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import uuid


DATABASE_PATH = Path(os.getenv("BRELOCK_DATABASE", Path(__file__).with_name("brelock.db")))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, expected_hex = encoded.split("$", 1)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 310_000
        )
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


@contextmanager
def connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                enrollment_token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admins (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                token_hash TEXT PRIMARY KEY,
                admin_id TEXT NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS laptops (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                hostname TEXT NOT NULL,
                platform TEXT NOT NULL,
                app_version TEXT NOT NULL,
                device_token_hash TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS brelocks (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                display_name TEXT NOT NULL,
                last_rssi INTEGER,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assignments (
                laptop_id TEXT PRIMARY KEY REFERENCES laptops(id) ON DELETE CASCADE,
                brelock_id TEXT NOT NULL UNIQUE REFERENCES brelocks(id) ON DELETE CASCADE,
                enabled INTEGER NOT NULL DEFAULT 1,
                rssi_threshold INTEGER NOT NULL DEFAULT -72,
                reaction_seconds REAL NOT NULL DEFAULT 3,
                reference_rssi INTEGER NOT NULL DEFAULT -59,
                watchdog_seconds REAL NOT NULL DEFAULT 6,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signal_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                laptop_id TEXT NOT NULL REFERENCES laptops(id) ON DELETE CASCADE,
                brelock_id TEXT NOT NULL REFERENCES brelocks(id) ON DELETE CASCADE,
                rssi INTEGER NOT NULL,
                recorded_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_laptops_company ON laptops(company_id);
            CREATE INDEX IF NOT EXISTS idx_brelocks_company ON brelocks(company_id);
            CREATE INDEX IF NOT EXISTS idx_samples_laptop_time
                ON signal_samples(laptop_id, recorded_at DESC);
            """
        )


def bootstrap_from_environment() -> dict:
    company_name = os.getenv("BRELOCK_COMPANY_NAME", "Demo Company").strip()
    company_slug = os.getenv("BRELOCK_COMPANY_SLUG", "demo").strip().lower()
    admin_email = os.getenv("BRELOCK_ADMIN_EMAIL", "admin@example.com").strip().lower()
    admin_password = os.getenv("BRELOCK_ADMIN_PASSWORD", "change-me-now")
    enrollment_token = os.getenv("BRELOCK_ENROLLMENT_TOKEN", "dev-enrollment-token")
    created = now_iso()

    with connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE slug = ?", (company_slug,)
        ).fetchone()
        if company is None:
            company_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO companies VALUES (?, ?, ?, ?, ?)",
                (company_id, company_name, company_slug, token_hash(enrollment_token), created),
            )
        else:
            company_id = company["id"]

        admin = conn.execute("SELECT id FROM admins WHERE email = ?", (admin_email,)).fetchone()
        if admin is None:
            conn.execute(
                "INSERT INTO admins VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, company_id, admin_email, password_hash(admin_password), created),
            )

    return {"company_slug": company_slug, "admin_email": admin_email}


def create_admin_session(email: str, password: str) -> tuple[str, dict] | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT admins.*, companies.name AS company_name, companies.slug AS company_slug
            FROM admins JOIN companies ON companies.id = admins.company_id
            WHERE admins.email = ?
            """,
            (email.strip().lower(),),
        ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        hours = int(os.getenv("BRELOCK_SESSION_HOURS", "12"))
        expires = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO admin_sessions VALUES (?, ?, ?)",
            (token_hash(token), row["id"], expires),
        )
        return token, dict(row)


def get_admin_by_session(token: str | None) -> dict | None:
    if not token:
        return None
    with connection() as conn:
        row = conn.execute(
            """
            SELECT admins.id, admins.email, admins.company_id,
                   companies.name AS company_name, companies.slug AS company_slug
            FROM admin_sessions
            JOIN admins ON admins.id = admin_sessions.admin_id
            JOIN companies ON companies.id = admins.company_id
            WHERE admin_sessions.token_hash = ? AND admin_sessions.expires_at > ?
            """,
            (token_hash(token), now_iso()),
        ).fetchone()
        return dict(row) if row else None


def delete_admin_session(token: str | None):
    if not token:
        return
    with connection() as conn:
        conn.execute("DELETE FROM admin_sessions WHERE token_hash = ?", (token_hash(token),))


def register_laptop(
    company_slug: str,
    enrollment_token: str,
    laptop_id: str,
    hostname: str,
    platform: str,
    app_version: str,
) -> str | None:
    with connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE slug = ?", (company_slug.strip().lower(),)
        ).fetchone()
        if company is None or not hmac.compare_digest(
            company["enrollment_token_hash"], token_hash(enrollment_token)
        ):
            return None

        device_token = secrets.token_urlsafe(32)
        timestamp = now_iso()
        existing = conn.execute(
            "SELECT id, company_id FROM laptops WHERE id = ?", (laptop_id,)
        ).fetchone()
        if existing and existing["company_id"] != company["id"]:
            return None
        if existing:
            conn.execute(
                """
                UPDATE laptops SET hostname=?, platform=?, app_version=?,
                    device_token_hash=?, last_seen=? WHERE id=? AND company_id=?
                """,
                (
                    hostname,
                    platform,
                    app_version,
                    token_hash(device_token),
                    timestamp,
                    laptop_id,
                    company["id"],
                ),
            )
        else:
            conn.execute(
                "INSERT INTO laptops VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    laptop_id,
                    company["id"],
                    hostname,
                    platform,
                    app_version,
                    token_hash(device_token),
                    timestamp,
                    timestamp,
                ),
            )
        return device_token


def get_laptop_by_token(token: str | None) -> dict | None:
    if not token:
        return None
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM laptops WHERE device_token_hash = ?", (token_hash(token),)
        ).fetchone()
        return dict(row) if row else None


def heartbeat(laptop: dict, observations: list[dict]):
    timestamp = now_iso()
    with connection() as conn:
        conn.execute("UPDATE laptops SET last_seen=? WHERE id=?", (timestamp, laptop["id"]))
        assignment = conn.execute(
            "SELECT brelock_id FROM assignments WHERE laptop_id=? AND enabled=1",
            (laptop["id"],),
        ).fetchone()
        for observation in observations:
            brelock_id = observation["brelock_id"].upper()
            existing = conn.execute(
                "SELECT company_id FROM brelocks WHERE id=?", (brelock_id,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO brelocks VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        brelock_id,
                        laptop["company_id"],
                        observation["display_name"],
                        observation["rssi"],
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
            elif existing["company_id"] == laptop["company_id"]:
                conn.execute(
                    "UPDATE brelocks SET display_name=?, last_rssi=?, last_seen=? WHERE id=?",
                    (observation["display_name"], observation["rssi"], timestamp, brelock_id),
                )
            if assignment and assignment["brelock_id"] == brelock_id:
                conn.execute(
                    "INSERT INTO signal_samples (laptop_id, brelock_id, rssi, recorded_at) VALUES (?, ?, ?, ?)",
                    (laptop["id"], brelock_id, observation["rssi"], timestamp),
                )
        # Telemetria służy do bieżącej diagnostyki, nie do trwałego śledzenia.
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds")
        conn.execute("DELETE FROM signal_samples WHERE recorded_at < ?", (cutoff,))


def get_client_config(laptop: dict) -> dict:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT assignments.*, brelocks.display_name
            FROM assignments JOIN brelocks ON brelocks.id = assignments.brelock_id
            WHERE assignments.laptop_id = ?
            """,
            (laptop["id"],),
        ).fetchone()
        if row is None:
            return {"assigned": False, "poll_seconds": 2}
        result = dict(row)
        result["assigned"] = True
        result["enabled"] = bool(result["enabled"])
        result["poll_seconds"] = 2
        return result


def admin_overview(company_id: str) -> dict:
    with connection() as conn:
        laptops = [
            dict(row)
            for row in conn.execute(
                """
                SELECT laptops.*, assignments.brelock_id, assignments.enabled,
                       assignments.rssi_threshold, assignments.reaction_seconds,
                       assignments.reference_rssi, assignments.watchdog_seconds
                FROM laptops LEFT JOIN assignments ON assignments.laptop_id = laptops.id
                WHERE laptops.company_id=? ORDER BY laptops.hostname COLLATE NOCASE
                """,
                (company_id,),
            )
        ]
        brelocks = [
            dict(row)
            for row in conn.execute(
                """
                SELECT brelocks.*, assignments.laptop_id
                FROM brelocks LEFT JOIN assignments ON assignments.brelock_id = brelocks.id
                WHERE brelocks.company_id=? ORDER BY brelocks.display_name COLLATE NOCASE
                """,
                (company_id,),
            )
        ]
        telemetry: dict[str, list[dict]] = {}
        rows = conn.execute(
            """
            SELECT signal_samples.laptop_id, signal_samples.rssi,
                   signal_samples.recorded_at
            FROM signal_samples
            JOIN laptops ON laptops.id=signal_samples.laptop_id
            WHERE laptops.company_id=?
            ORDER BY signal_samples.recorded_at DESC LIMIT 2000
            """,
            (company_id,),
        )
        for row in rows:
            samples = telemetry.setdefault(row["laptop_id"], [])
            if len(samples) < 90:
                samples.append({"rssi": row["rssi"], "recorded_at": row["recorded_at"]})
        for samples in telemetry.values():
            samples.reverse()
        return {"laptops": laptops, "brelocks": brelocks, "telemetry": telemetry}


def assign_brelock(company_id: str, laptop_id: str, brelock_id: str):
    timestamp = now_iso()
    with connection() as conn:
        laptop = conn.execute(
            "SELECT id FROM laptops WHERE id=? AND company_id=?", (laptop_id, company_id)
        ).fetchone()
        brelock = conn.execute(
            "SELECT id FROM brelocks WHERE id=? AND company_id=?",
            (brelock_id.upper(), company_id),
        ).fetchone()
        if not laptop or not brelock:
            raise ValueError("Laptop lub breLock nie istnieje w tej firmie")
        owner = conn.execute(
            "SELECT laptop_id FROM assignments WHERE brelock_id=?", (brelock_id.upper(),)
        ).fetchone()
        if owner and owner["laptop_id"] != laptop_id:
            raise ValueError("Ten breLock jest już przypisany do innego laptopa")
        conn.execute(
            """
            INSERT INTO assignments (laptop_id, brelock_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(laptop_id) DO UPDATE SET brelock_id=excluded.brelock_id,
                updated_at=excluded.updated_at
            """,
            (laptop_id, brelock_id.upper(), timestamp),
        )



def update_assignment(company_id: str, laptop_id: str, settings: dict):
    with connection() as conn:
        row = conn.execute(
            """
            SELECT assignments.laptop_id FROM assignments
            JOIN laptops ON laptops.id=assignments.laptop_id
            WHERE assignments.laptop_id=? AND laptops.company_id=?
            """,
            (laptop_id, company_id),
        ).fetchone()
        if not row:
            raise ValueError("Laptop nie ma przypisanego breLocka")
        conn.execute(
            """
            UPDATE assignments SET enabled=?, rssi_threshold=?, reaction_seconds=?,
                reference_rssi=?, watchdog_seconds=?, updated_at=? WHERE laptop_id=?
            """,
            (
                int(settings["enabled"]),
                settings["rssi_threshold"],
                settings["reaction_seconds"],
                settings["reference_rssi"],
                settings["watchdog_seconds"],
                now_iso(),
                laptop_id,
            ),
        )


def unassign_brelock(company_id: str, laptop_id: str):
    with connection() as conn:
        conn.execute(
            """
            DELETE FROM assignments WHERE laptop_id IN
            (SELECT id FROM laptops WHERE id=? AND company_id=?)
            """,
            (laptop_id, company_id),
        )


def add_brelock(company_id: str, brelock_id: str, display_name: str):
    timestamp = now_iso()
    normalized = brelock_id.replace(":", "").replace("-", "").strip().upper()
    if len(normalized) != 12 or any(char not in "0123456789ABCDEF" for char in normalized):
        raise ValueError("ID breLocka musi zawierać 12 znaków szesnastkowych")
    with connection() as conn:
        existing = conn.execute(
            "SELECT company_id FROM brelocks WHERE id=?", (normalized,)
        ).fetchone()
        if existing and existing["company_id"] != company_id:
            raise ValueError("Ten breLock jest już zarejestrowany w innej firmie")
        conn.execute(
            """
            INSERT INTO brelocks VALUES (?, ?, ?, NULL, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name
            """,
            (normalized, company_id, display_name.strip() or f"breLock-{normalized[-6:]}", timestamp, timestamp, timestamp),
        )
