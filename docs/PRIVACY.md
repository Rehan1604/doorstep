# Privacy

Doorstep handles what you notice outdoors and how you feel. Here is exactly where it goes.

## What is collected

Your time, energy, interest and solo/group choices; the generated mission; your typed note; a "how I felt" rating; the reflection; mission and note vectors; learned style preferences.

## Local mode (default)

| | |
|---|---|
| Stored | `backend/doorstep.db` (SQLite) on your machine |
| Leaves the machine | **Nothing.** Browser → `localhost` backend → `localhost` Ollama |
| Accounts | None |
| Delete your data | Stop the backend and delete `doorstep.db` |

## Hosted demo

| | |
|---|---|
| Stored | SQLite on our Render server, keyed to a random ID kept in your browser (no account) |
| Leaves the machine | Your choices, recent mission titles, your note, and related earlier notes are sent to Render and to Groq to generate text |
| Retention | Free-tier storage can reset on redeploy or restart |
| Delete your data | Not supported yet |

If you care about privacy, use local mode. That is the point of the project.

## Other notes

- Optional voice notes (`faster-whisper`) run locally. Audio is not stored.
- Stored text is cleaned before it is placed into prompts.
- The backend only accepts requests from `localhost` and the configured frontend origin.
- No API keys are in this repository. Hosted keys live in the host's dashboard.