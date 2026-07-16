from __future__ import annotations

import uuid
from typing import Literal
import json
import os

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# -- App -------------------------------------------------------------------

app = FastAPI(title="CyberSwipe API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- In-memory stores ------------------------------------------------------

sessions: dict[str, dict] = {}

FAKE_PLAYERS: list[dict] = [
    {"nick": "h4ck3rm4n", "score": 2750},
    {"nick": "CyberKasia", "score": 2100},
    {"nick": "NetNinja", "score": 1800},
    {"nick": "PhishSlayer", "score": 1500},
    {"nick": "ByteQueen", "score": 1350},
    {"nick": "ZeroDay_Kuba", "score": 1100},
    {"nick": "SecOps_Ania", "score": 950},
    {"nick": "FirewallFan", "score": 800},
    {"nick": "TokenTomek", "score": 600},
    {"nick": "PatchMonday", "score": 400},
]

# -- Tasks (Quishing + AI images) ------------------------------------------

TASKS: list[dict] = []
if os.path.exists("tasks.json"):
    with open("tasks.json", "r", encoding="utf-8") as f:
        TASKS = json.load(f)
else:
    print("Warning: tasks.json not found.", flush=True)

# -- Pydantic models -------------------------------------------------------


class LoginRequest(BaseModel):
    nick: str


class LoginResponse(BaseModel):
    token: str
    nick: str


class SwipeRequest(BaseModel):
    task_id: int
    action: Literal["scan", "ignore", "image_1", "image_2", "image_3", "image_4", "skip"]


class SwipeResponse(BaseModel):
    correct: bool
    points_earned: int
    total_score: int
    combo: int
    explanation: str


class TaskOut(BaseModel):
    id: int
    type: str
    title: str
    description: str
    hint: str
    category: str
    location: str
    risk_level: str
    images: list[str] | None = None


class LeaderboardEntry(BaseModel):
    rank: int
    nick: str
    score: int
    is_current_user: bool


# -- Helpers ----------------------------------------------------------------

BASE_POINTS = 100


def _get_session(token: str | None) -> dict:
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Nie jestes zalogowany.")
    return sessions[token]


# -- Endpoints --------------------------------------------------------------


@app.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest):
    nick = body.nick.strip()
    if not nick:
        raise HTTPException(status_code=400, detail="Nick nie moze byc pusty.")

    for tok, sess in sessions.items():
        if sess["nick"] == nick:
            return LoginResponse(token=tok, nick=nick)

    token = uuid.uuid4().hex
    sessions[token] = {
        "nick": nick,
        "score": 0,
        "combo": 0,
        "answered_ids": [],
    }
    return LoginResponse(token=token, nick=nick)


@app.get("/api/tasks", response_model=list[TaskOut])
def get_tasks(x_token: str | None = Header(None)):
    session = _get_session(x_token)
    answered = set(session["answered_ids"])
    return [
        TaskOut(
            id=t["id"],
            type=t["type"],
            title=t["title"],
            description=t["description"],
            hint=t["hint"],
            category=t.get("category", t.get("type", "mixed")),
            location=t.get("location", "Internet"),
            risk_level=t["risk_level"],
            images=t.get("images", None)
        )
        for t in TASKS
        if t["id"] not in answered
    ]


@app.post("/api/swipe", response_model=SwipeResponse)
def swipe(body: SwipeRequest, x_token: str | None = Header(None)):
    session = _get_session(x_token)

    task = next((t for t in TASKS if t["id"] == body.task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="Zadanie nie istnieje.")

    if body.task_id in session["answered_ids"]:
        raise HTTPException(status_code=400, detail="Juz odpowiedziales na to pytanie.")

    # Action "skip" bypasses scoring, resets combo but adds question to answered
    if body.action == "skip":
        session["combo"] = 0
        session["answered_ids"].append(body.task_id)
        return SwipeResponse(
            correct=False,
            points_earned=0,
            total_score=session["score"],
            combo=0,
            explanation="Pominieto pytanie. Twoje combo zostalo wyzerowane."
        )

    correct = body.action == task["correct_action"]

    if correct:
        session["combo"] += 1
        multiplier = min(session["combo"], 5)  # cap at 5x
        points = BASE_POINTS * multiplier
    else:
        session["combo"] = 0
        points = 0

    session["score"] += points
    session["answered_ids"].append(body.task_id)

    return SwipeResponse(
        correct=correct,
        points_earned=points,
        total_score=session["score"],
        combo=session["combo"],
        explanation=task.get("explanation_correct", task.get("explanation", "")) if correct else task.get("explanation_incorrect", task.get("explanation", "")),
    )


@app.get("/api/leaderboard", response_model=list[LeaderboardEntry])
def leaderboard(x_token: str | None = Header(None)):
    session = _get_session(x_token)

    entries: list[dict] = []
    for fp in FAKE_PLAYERS:
        entries.append({"nick": fp["nick"], "score": fp["score"], "is_current_user": False})

    already = False
    for e in entries:
        if e["nick"] == session["nick"]:
            e["score"] = max(e["score"], session["score"])
            e["is_current_user"] = True
            already = True
            break
    if not already:
        entries.append({"nick": session["nick"], "score": session["score"], "is_current_user": True})

    entries.sort(key=lambda e: e["score"], reverse=True)

    return [
        LeaderboardEntry(rank=i + 1, nick=e["nick"], score=e["score"], is_current_user=e["is_current_user"])
        for i, e in enumerate(entries)
    ]


@app.get("/api/stats")
def stats(x_token: str | None = Header(None)):
    session = _get_session(x_token)
    total_tasks = len(TASKS)
    answered = len(session["answered_ids"])
    return {
        "nick": session["nick"],
        "score": session["score"],
        "combo": session["combo"],
        "answered": answered,
        "total_tasks": total_tasks,
        "progress_pct": round(answered / total_tasks * 100) if total_tasks else 0,
    }
