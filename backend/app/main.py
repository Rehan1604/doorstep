import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import ai, store, voice
from .schema import Completion, Mission, MissionRequest

@asynccontextmanager
async def lifespan(_):
    threading.Thread(target=ai.warmup, daemon=True).start()
    yield


app = FastAPI(title="Doorstep", version="0.1.0", lifespan=lifespan)
# Local-only: the UI dev server is the sole allowed origin.
import os

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        FRONTEND_URL,
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Client-Id"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "voice": voice.available(), **ai.model_status()}


@app.post("/api/missions")
def create_mission(req: MissionRequest, x_client_id: str = Header(default="", max_length=64)):
    mission, source = ai.generate_mission(req, store.recent_titles(client=x_client_id))
    mid = store.save_mission(req.model_dump(), mission.model_dump(), source, x_client_id)
    return {"id": mid, "source": source, "mission": mission}



@app.post("/api/missions/{mid}/complete")
def complete_mission(mid: int, body: Completion, x_client_id: str = Header(default="", max_length=64)):
    row = store.get_mission(mid)
    if not row or row["client"] != x_client_id:
        raise HTTPException(404, "mission not found")
    text, source = ai.generate_reflection(Mission(**row["mission"]), body.completed, body.surprise)
    store.complete(mid, body.completed, body.surprise, body.feeling, text)
    return {"reflection": text, "source": source}

@app.get("/api/history")
def get_history(x_client_id: str = Header(default="", max_length=64)):
    return store.history(x_client_id)


@app.post("/api/transcribe")
async def transcribe(request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(400, "empty audio")
    if len(data) > voice.MAX_BYTES:
        raise HTTPException(413, "audio too large")
    try:
        return {"text": voice.transcribe(data)}
    except voice.VoiceUnavailable:
        raise HTTPException(503, "voice not installed")
    except Exception:
        raise HTTPException(422, "could not read audio")
