import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import ai, engine, store, voice
from .schema import Completion, MissionRequest


@asynccontextmanager
async def lifespan(_):
    threading.Thread(target=ai.warmup, daemon=True).start()
    yield


app = FastAPI(title="Doorstep", version="0.2.0", lifespan=lifespan)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", FRONTEND_URL],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Client-Id"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "voice": voice.available(), **ai.model_status()}


@app.post("/api/missions")
def create_mission(req: MissionRequest, x_client_id: str = Header(default="", max_length=64)):
    return engine.create(req, x_client_id)


@app.post("/api/missions/{mid}/complete")
def complete_mission(mid: int, body: Completion, x_client_id: str = Header(default="", max_length=64)):
    result = engine.finish(mid, body, x_client_id)
    if result is None:
        raise HTTPException(404, "mission not found")
    return result


@app.get("/api/history")
def get_history(x_client_id: str = Header(default="", max_length=64)):
    return store.history(x_client_id)


@app.get("/api/insights")
def get_insights(x_client_id: str = Header(default="", max_length=64)):
    return engine.insights(x_client_id)


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