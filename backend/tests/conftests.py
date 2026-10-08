import pytest

from app import config
from app.ml import embed


@pytest.fixture(autouse=True)
def deterministic_embeddings(monkeypatch):
    """Tests never touch a real embedding model."""
    monkeypatch.setattr(config, "EMBED_PROVIDER", "hash")
    monkeypatch.setattr(embed, "_down_until", 0.0)