# Architecture

```
 Browser (React PWA, localhost:5173)
   │  /api (Vite proxy)
   ▼
 FastAPI (localhost:8000)  ── CORS: localhost only
   ├─ schema.py     input validation, interest sanitizing
   ├─ ai.py         prompt → Ollama → JSON validate → safety screen → retry
   │                         │ fail ▼
   ├─ fallback.py   hand-written missions and reflections
   └─ store.py      SQLite (doorstep.db), local only
   │
   ▼
 Ollama (localhost:11434) → qwen2.5:1.5b-instruct, CPU, kept warm 30 min

 Optional: voice.py → faster-whisper (CPU), only if installed
```

Nothing in this diagram crosses the network boundary of the machine.