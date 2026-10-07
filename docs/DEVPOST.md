## Project Name
Doorstep

## Elevator Pitch
Doorstep is a mission app that uses a local open-weight model to write you one small outdoor task, so people can leave the screen within a minute without sending a single observation to the cloud.

## Project Story
**The problem.** Every app wants more of your time on screen, including the ones that say they want you outside.

**The insight.** An AI doesn't have to keep you talking. It can do its job and get out of the way.

**The solution.** Doorstep gives you a 45-second screen budget. You pick your time, energy, and interest. A local model writes one concrete mission. The bar counts down, and at zero the app goes black with one instruction and a timer. You come back, type what surprised you, and get two sentences of reflection. No feed, no chat, no streaks.

**Why open AI.** The model runs through Ollama on a CPU-only laptop. What you notice outdoors never leaves your machine, it works with Wi-Fi off, and it costs nothing per mission. We benchmarked qwen2.5:1.5b-instruct against phi3.5 on that laptop: both gave valid JSON every time, but Qwen took 11.4 s median versus 29.4 s, so latency decided it.

**How we built it.** FastAPI, Pydantic schemas, retries, a safety screen on model output, hand-written fallbacks, SQLite, and a React/Vite front end. 13 backend and 5 frontend tests.

**What happens offline.** The status strip flips to INTERNET: DISCONNECTED while the AI stays LOCAL, and missions keep generating.

**What we learned.** Slow local inference can become a feature if you design the wait. And fallbacks matter more than the model.

**What's next.** Optional weather awareness, a phone lock mode, group missions.