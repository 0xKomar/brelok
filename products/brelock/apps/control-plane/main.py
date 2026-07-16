from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import re
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import db


STATIC_DIR = Path(__file__).with_name("static")
COOKIE_NAME = "brelock_admin_session"
BRELOCK_ID_PATTERN = re.compile(r"^[0-9A-F]{12}$")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_database()
    info = db.bootstrap_from_environment()
    print(
        f"[control-plane] company={info['company_slug']} admin={info['admin_email']}",
        flush=True,
    )
    yield


app = FastAPI(title="breLock Control Plane", version="0.2.0", lifespan=lifespan)


class LoginBody(BaseModel):
    email: str
    password: str


class LaptopRegistration(BaseModel):
    company_slug: str = Field(min_length=2, max_length=60)
    enrollment_token: str = Field(min_length=8, max_length=256)
    laptop_id: str = Field(pattern=r"^[0-9A-Fa-f]{32}$")
    hostname: str = Field(min_length=1, max_length=120)
    platform: str = Field(min_length=1, max_length=80)
    app_version: str = Field(min_length=1, max_length=30)


class Observation(BaseModel):
    brelock_id: str = Field(pattern=r"^[0-9A-Fa-f]{12}$")
    display_name: str = Field(min_length=1, max_length=40)
    rssi: int = Field(ge=-127, le=20)


class HeartbeatBody(BaseModel):
    observations: list[Observation] = Field(default_factory=list, max_length=100)


class AssignmentBody(BaseModel):
    laptop_id: str = Field(pattern=r"^[0-9A-Fa-f]{32}$")
    brelock_id: str = Field(pattern=r"^[0-9A-Fa-f]{12}$")


class AssignmentSettings(BaseModel):
    enabled: bool = True
    rssi_threshold: int = Field(ge=-100, le=-35)
    reaction_seconds: float = Field(ge=1, le=30)
    reference_rssi: int = Field(ge=-90, le=-35)
    watchdog_seconds: float = Field(ge=2, le=60)


class ManualBrelock(BaseModel):
    brelock_id: str
    display_name: str = Field(default="", max_length=40)


def require_admin(
    session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> dict:
    admin = db.get_admin_by_session(session)
    if not admin:
        raise HTTPException(status_code=401, detail="Sesja administratora wygasła")
    return admin


def require_laptop(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Brak tokenu laptopa")
    laptop = db.get_laptop_by_token(authorization[7:].strip())
    if not laptop:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token laptopa")
    return laptop


@app.get("/", include_in_schema=False)
def admin_page():
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "brelock-control-plane"}


@app.post("/api/admin/login")
def admin_login(body: LoginBody, response: Response):
    result = db.create_admin_session(body.email, body.password)
    if not result:
        raise HTTPException(status_code=401, detail="Nieprawidłowy email lub hasło")
    token, admin = result
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        secure=os.getenv("BRELOCK_SECURE_COOKIE", "0") == "1",
        max_age=int(os.getenv("BRELOCK_SESSION_HOURS", "12")) * 3600,
        path="/",
    )
    return {
        "email": admin["email"],
        "company_name": admin["company_name"],
        "company_slug": admin["company_slug"],
    }


@app.post("/api/admin/logout", status_code=204)
def admin_logout(
    response: Response,
    session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
):
    db.delete_admin_session(session)
    response.delete_cookie(COOKIE_NAME, path="/")


@app.get("/api/admin/me")
def admin_me(admin: Annotated[dict, Depends(require_admin)]):
    return admin


@app.get("/api/admin/overview")
def overview(admin: Annotated[dict, Depends(require_admin)]):
    return db.admin_overview(admin["company_id"])


@app.post("/api/admin/assign", status_code=204)
def assign(body: AssignmentBody, admin: Annotated[dict, Depends(require_admin)]):
    try:
        db.assign_brelock(admin["company_id"], body.laptop_id, body.brelock_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/admin/laptops/{laptop_id}/settings", status_code=204)
def settings(
    laptop_id: str,
    body: AssignmentSettings,
    admin: Annotated[dict, Depends(require_admin)],
):
    try:
        db.update_assignment(admin["company_id"], laptop_id, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/admin/laptops/{laptop_id}/assignment", status_code=204)
def unassign(laptop_id: str, admin: Annotated[dict, Depends(require_admin)]):
    db.unassign_brelock(admin["company_id"], laptop_id)


@app.post("/api/admin/brelocks", status_code=204)
def create_brelock(
    body: ManualBrelock, admin: Annotated[dict, Depends(require_admin)]
):
    try:
        db.add_brelock(admin["company_id"], body.brelock_id, body.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/client/register")
def client_register(body: LaptopRegistration):
    token = db.register_laptop(
        body.company_slug,
        body.enrollment_token,
        body.laptop_id,
        body.hostname,
        body.platform,
        body.app_version,
    )
    if not token:
        raise HTTPException(status_code=403, detail="Nieprawidłowy kod wdrożeniowy firmy")
    return {"device_token": token}


@app.post("/api/client/heartbeat", status_code=204)
def client_heartbeat(
    body: HeartbeatBody, laptop: Annotated[dict, Depends(require_laptop)]
):
    db.heartbeat(laptop, [observation.model_dump() for observation in body.observations])


@app.get("/api/client/config")
def client_config(laptop: Annotated[dict, Depends(require_laptop)]):
    return db.get_client_config(laptop)
