import pytest
from app.core.config import settings
from app.features.documents import processing_service
from app.workers.celery_app import celery_app


def _fake_embeddings(texts: list[str]) -> list[list[float]]:
    return [[1.0, 0.0, 0.0] for _ in texts]


@pytest.fixture(autouse=True)
def use_fake_local_embeddings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "document_storage_backend", "local")
    monkeypatch.setattr(
        settings, "local_document_storage_path", str(tmp_path / "document_uploads")
    )
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    monkeypatch.setattr(
        "app.features.documents.router.embed_texts",
        _fake_embeddings,
    )
    monkeypatch.setattr(processing_service, "embed_texts", _fake_embeddings)
