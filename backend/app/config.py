import os

AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama")

MODEL = os.getenv(
    "DOORSTEP_MODEL",
    "qwen2.5:1.5b-instruct"
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
)

TIMEOUT_S = float(
    os.getenv("MODEL_TIMEOUT_S", "45")
)

DB_PATH = os.getenv(
    "DOORSTEP_DB",
    "doorstep.db"
)

MAX_RETRIES = 2