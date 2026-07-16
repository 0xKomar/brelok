from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


APP_VERSION = "0.2.0"


class ControlPlaneError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _app_data_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.getenv("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "breLock"


def _deployment_path() -> Path:
    configured = os.getenv("BRELOCK_DEPLOYMENT_FILE")
    if configured:
        return Path(configured).expanduser()
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return base / "deployment.json"


def load_deployment() -> dict:
    data = {}
    path = _deployment_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlPlaneError(f"Nieprawidłowy plik wdrożeniowy: {exc}") from exc
    return {
        "control_url": os.getenv(
            "BRELOCK_CONTROL_URL", data.get("control_url", "http://127.0.0.1:8100")
        ).rstrip("/"),
        "company_slug": os.getenv(
            "BRELOCK_COMPANY_SLUG", data.get("company_slug", "demo")
        ),
        "enrollment_token": os.getenv(
            "BRELOCK_ENROLLMENT_TOKEN", data.get("enrollment_token", "")
        ),
    }


class ControlPlaneClient:
    def __init__(self):
        self.deployment = load_deployment()
        self.state_path = _app_data_dir() / "client-state.json"
        self.state = self._load_state()

    @property
    def installation_id(self) -> str:
        return self.state["installation_id"]

    @property
    def control_url(self) -> str:
        return self.deployment["control_url"]

    def _load_state(self) -> dict:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
        if not state.get("installation_id"):
            state["installation_id"] = uuid.uuid4().hex
            self._save_state(state)
        return state

    def _save_state(self, state: dict | None = None):
        if state is not None:
            self.state = state
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)
        if os.name != "nt":
            self.state_path.chmod(0o600)

    def _request(self, path: str, method: str = "GET", body: dict | None = None):
        headers = {"Accept": "application/json"}
        token = self.state.get("device_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.control_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=8) as response:
                payload = response.read()
                return json.loads(payload) if payload else None
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get("detail", str(exc))
            except Exception:
                detail = str(exc)
            raise ControlPlaneError(detail, exc.code) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ControlPlaneError(f"Brak połączenia z panelem: {exc}") from exc

    def ensure_registered(self):
        if self.state.get("device_token"):
            return
        enrollment_token = self.deployment.get("enrollment_token", "")
        if not enrollment_token:
            raise ControlPlaneError(
                "Brak konfiguracji firmy. Administrator musi dostarczyć deployment.json."
            )
        result = self._request(
            "/api/client/register",
            "POST",
            {
                "company_slug": self.deployment["company_slug"],
                "enrollment_token": enrollment_token,
                "laptop_id": self.installation_id,
                "hostname": socket.gethostname(),
                "platform": f"{platform.system()} {platform.release()}",
                "app_version": APP_VERSION,
            },
        )
        self.state["device_token"] = result["device_token"]
        self._save_state()

    def fetch_config(self) -> dict:
        try:
            config = self._request("/api/client/config")
            self.state["cached_config"] = config
            self._save_state()
            return config
        except ControlPlaneError as exc:
            if exc.status == 401:
                self.state.pop("device_token", None)
                self._save_state()
            raise

    def cached_config(self) -> dict | None:
        return self.state.get("cached_config")

    def heartbeat(self, observations: list[dict]):
        self._request(
            "/api/client/heartbeat", "POST", {"observations": observations}
        )
