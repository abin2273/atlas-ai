from functools import lru_cache

import numpy as np
from sentence_transformers import CrossEncoder

from app.core.config import settings


class RerankingError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _model() -> CrossEncoder:
    try:
        return CrossEncoder(settings.reranker_model_name, device="cpu")
    except Exception as error:
        raise RerankingError(
            f"Could not load local reranker model '{settings.reranker_model_name}'"
        ) from error


def rerank_texts(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    try:
        scores = np.asarray(
            _model().predict(
                [(query, passage) for passage in passages],
                batch_size=16,
                show_progress_bar=False,
            )
        ).reshape(-1)
    except Exception as error:
        raise RerankingError("Local cross-encoder reranking failed") from error

    if scores.size != len(passages):
        raise RerankingError("Reranker returned an invalid score batch")
    if not np.isfinite(scores).all():
        raise RerankingError("Reranker returned non-finite scores")
    return scores.astype(np.float32).tolist()
