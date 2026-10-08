"""Text embeddings for semantic memory and novelty checks.

Local mode: an open embedding model through Ollama (default all-minilm, CPU-friendly).
Fallback / hosted mode: a deterministic hashed bag-of-words + character-trigram vector.
Vectors from different embedders are never compared; each stored vector carries its embedder name.
"""
import logging
import math
import re
import time
import zlib

import httpx

from .. import config

log = logging.getLogger("doorstep.embed")
DIM = 256
HASH_NAME = "hash256"
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"a", "an", "the", "and", "or", "to", "of", "in", "on", "at", "for", "with", "your", "you",
         "it", "is", "are", "as", "by", "be", "this", "that", "then", "one", "each"}
_down_until = 0.0

# Cosine cut-offs per embedder (hashed vectors are lexical, so their scale differs).
NOVELTY_LIMIT = {HASH_NAME: 0.60}
NOVELTY_DEFAULT = 0.85
RECALL_MIN = {HASH_NAME: 0.20}
RECALL_DEFAULT = 0.45


def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _hash_vec(text: str) -> list[float]:
    vec = [0.0] * DIM

    def add(feat: str, wt: float) -> None:
        h = zlib.crc32(feat.encode())
        vec[h % DIM] += wt if (h >> 16) & 1 else -wt

    for w in (w for w in _WORD.findall(text.lower()) if w not in _STOP):
        add("w:" + w, 1.0)
        p = f"^{w}$"
        for i in range(len(p) - 2):
            add("c:" + p[i:i + 3], 0.4)
    return _norm(vec)


def _provider() -> str:
    p = config.EMBED_PROVIDER.lower()
    if p == "auto":
        return "ollama" if config.AI_PROVIDER.lower() == "ollama" else "hash"
    return p


def embed(text: str) -> tuple[list[float], str]:
    """Returns (unit vector, embedder name). Never raises."""
    global _down_until
    text = text.strip()[:1000] or "empty"
    if _provider() == "ollama" and time.time() >= _down_until:
        try:
            r = httpx.post(f"{config.OLLAMA_URL}/api/embed",
                           json={"model": config.EMBED_MODEL, "input": text, "keep_alive": "30m"}, timeout=8)
            r.raise_for_status()
            return _norm(r.json()["embeddings"][0]), f"ollama:{config.EMBED_MODEL}"
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            _down_until = time.time() + 30  # don't retry a dead/missing model on every call
            log.info("embedding model unavailable, using hashed vectors")
    return _hash_vec(text), HASH_NAME


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) if len(a) == len(b) else 0.0


def novelty_limit(embedder: str) -> float:
    return NOVELTY_LIMIT.get(embedder, NOVELTY_DEFAULT)


def recall_min(embedder: str) -> float:
    return RECALL_MIN.get(embedder, RECALL_DEFAULT)