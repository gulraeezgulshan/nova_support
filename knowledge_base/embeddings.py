"""Text embeddings for semantic retrieval.

`fastembed` runs an ONNX model on CPU (no GPU, no external API key). The `hash` provider is
a deterministic bag-of-words feature-hashing embedder used in tests and offline development.
"""

import hashlib
import math
import re
from functools import lru_cache
from typing import Any, Protocol

from src.core.config import get_settings

_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str, dim: int):
        self.model_name = model_name
        self.dim = dim
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding  # heavy import, loaded on first use

            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._load().passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return [float(x) for x in next(iter(self._load().query_embed([text])))]


class HashEmbedder:
    def __init__(self, dim: int):
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedding_provider == "hash":
        return HashEmbedder(settings.embedding_dim)
    return FastEmbedEmbedder(settings.embedding_model, settings.embedding_dim)
