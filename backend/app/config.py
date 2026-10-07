import os

MODEL = os.getenv("DOORSTEP_MODEL", "qwen2.5:1.5b-instruct")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
TIMEOUT_S = float(os.getenv("MODEL_TIMEOUT_S", "45"))
DB_PATH = os.getenv("DOORSTEP_DB", "doorstep.db")
MAX_RETRIES = 2
