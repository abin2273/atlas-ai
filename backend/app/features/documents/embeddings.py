from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class EmbeddingError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    try:
        return SentenceTransformer(settings.embedding_model_name, device="cpu")
    except Exception as error:
        raise EmbeddingError(
            f"Could not load local embedding model '{settings.embedding_model_name}'"
        ) from error


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        vectors = _model().encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    except Exception as error:
        raise EmbeddingError("Local text embedding failed") from error

    if vectors.ndim != 2 or vectors.shape[0] != len(texts):
        raise EmbeddingError("Embedding model returned an invalid vector batch")
    if not np.isfinite(vectors).all():
        raise EmbeddingError("Embedding model returned non-finite vector values")
    return vectors.astype(np.float32).tolist()
