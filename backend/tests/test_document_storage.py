from pathlib import Path

import pytest
from app.core.config import settings
from app.features.documents.storage import (
    DocumentStorageError,
    LocalDocumentStorage,
    S3DocumentStorage,
)


def test_local_document_storage_round_trips_and_deletes(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    key = "organizations/org-id/documents/doc-id/source"
    storage.put(key, b"document bytes")
    assert storage.get(key) == b"document bytes"
    storage.delete(key)
    with pytest.raises(DocumentStorageError, match="Could not read"):
        storage.get(key)


def test_local_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    with pytest.raises(DocumentStorageError, match="Invalid document storage key"):
        storage.put("../outside", b"unsafe")
    assert not (tmp_path.parent / "outside").exists()


def test_s3_storage_uses_configured_bucket_and_key(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class Body:
        def read(self) -> bytes:
            return b"s3 bytes"

    class Client:
        def put_object(self, **kwargs) -> None:
            calls.append(("put", kwargs))

        def get_object(self, **kwargs) -> dict[str, Body]:
            calls.append(("get", kwargs))
            return {"Body": Body()}

        def delete_object(self, **kwargs) -> None:
            calls.append(("delete", kwargs))

    monkeypatch.setattr(settings, "s3_bucket", "atlas-test")
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://object-store")
    monkeypatch.setattr(
        "app.features.documents.storage.boto3.client", lambda *a, **k: Client()
    )
    storage = S3DocumentStorage()
    key = "organizations/org/documents/doc/source"
    storage.put(key, b"s3 bytes")
    assert storage.get(key) == b"s3 bytes"
    storage.delete(key)
    assert [name for name, _ in calls] == ["put", "get", "delete"]
    assert all(call["Bucket"] == "atlas-test" for _, call in calls)
    assert all(call["Key"] == key for _, call in calls)
