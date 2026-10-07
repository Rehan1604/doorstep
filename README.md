# Doorstep

The AI app that is over the moment you cross your own doorstep.

Doorstep writes you one small outdoor mission with a local open-weight model, gives you 45 seconds of screen time to read it, then goes black. You come back, type what surprised you, and get a two-line reflection. The app's success metric is that you stop using it.

## The Problem
Apps optimize for time on screen. Even "get outside" apps keep you scrolling inside them.

## The Idea
A hard screen budget. Each mission gives you 45 seconds of screen. If the bar hits zero, the app launches outdoor mode on its own: a black screen with one instruction and a timer.

## Why Open AI?
- **Your observations stay on your machine.** What surprised you outdoors is written to a local SQLite file. No account, no cloud.
- **Works with Wi-Fi off.** The top strip flips to `INTERNET: DISCONNECTED · AI: LOCAL`, and missions still generate. That is what remote places need.
- **Zero per-call cost.** Missions and reflections cost nothing to generate.
- **Swappable model.** Set `DOORSTEP_MODEL` and restart. We benchmarked two models (below) and chose with data.
- **Inspectable prompts.** Every prompt is in `backend/app/ai.py`.

## How It Works
Home (time, energy, interest) → local model → validated JSON mission → 45s card → PHONE DOWN → typed note → reflection → history.

## Architecture
See `docs/ARCHITECTURE.md`.

## Local / Offline Mode
Works offline: mission generation, reflections, history, saved data, the whole UI.
Needs nothing optional: there are no maps, weather, or sync in this version.
If the model is missing or fails, hand-written fallback missions are served and marked "OFFLINE-SAFE MISSION".

## Privacy
- Collected: your time/energy/interest choices, the generated mission, your typed note, a feeling rating, the reflection.
- Stored: `doorstep.db` (SQLite) in `backend/`.
- Leaves the machine: nothing. The only network calls are browser → `localhost` backend → `localhost` Ollama.
- Optional voice (if you install `faster-whisper`) also runs locally.

## Tech Stack
FastAPI, Pydantic, SQLite, httpx, Ollama, React 18, Vite. Optional: faster-whisper.

## Installation
```bash
git clone <your-repo-url> && cd doorstep
ollama pull qwen2.5:1.5b-instruct
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

## Running Locally
```bash
# terminal 1
cd backend && uvicorn app.main:app --port 8000
# terminal 2
cd frontend && npm run dev     # open http://localhost:5173
```
Tests:
```bash
cd backend && python -m pytest -q
cd frontend && npm test
```

## Model Setup
Default: `qwen2.5:1.5b-instruct`. Change with the `DOORSTEP_MODEL` env var (see `.env.example`).
Benchmark on your hardware: `python ai/benchmark.py qwen2.5:1.5b-instruct phi3.5 --runs 10`

## Technical Decisions
Measured on a Core i5-13420H laptop, 16 GB RAM, CPU only, 10 runs each:

| Model | Valid JSON | Safe output | Median | p90 |
|---|---|---|---|---|
| qwen2.5:1.5b-instruct | 100% | 100% | 11.4 s | 13.7 s |
| phi3.5 | 100% | 100% | 29.4 s | 41.4 s |

Both were reliable, so latency decided it. The 11 s wait is shown as a breathing screen instead of a spinner.

- Output is constrained by a JSON schema, validated with Pydantic, retried twice, and screened for unsafe content (climbing, private property, wildlife contact, and similar). Failures fall back to a hand-written mission.
- Prompts include only the current constraints and the last three mission titles, never full history.

## Challenges
CPU-only inference is slow, so the wait became part of the design. A model-server outage must never crash the UI, so every AI call has a fallback.

## Future Work
Weather-aware missions (optional online), phone lock mode, group missions, more models.

## Contributing
Issues and PRs welcome.

## License
MIT. Check the model card for the license of whichever model you pull.