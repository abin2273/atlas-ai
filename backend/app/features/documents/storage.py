from pathlib import Path, PurePosixPath
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class DocumentStorageError(RuntimeError):
    pass


class DocumentStorage(Protocol):
    def put(self, key: str, content: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


def _validate_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise DocumentStorageError("Invalid document storage key")
    return path


class LocalDocumentStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = self.root.joinpath(*_validate_key(key).parts).resolve()
        if not path.is_relative_to(self.root):
            raise DocumentStorageError("Document storage key escapes the storage root")
        return path

    def put(self, key: str, content: bytes) -> None:
        try:
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        except OSError as error:
            raise DocumentStorageError(
                "Could not store the uploaded document"
            ) from error

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except OSError as error:
            raise DocumentStorageError("Could not read the stored document") from error

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as error:
            raise DocumentStorageError(
                "Could not delete the stored document"
            ) from error


class S3DocumentStorage:
    def __init__(self) -> None:
        if not settings.s3_bucket:
            raise DocumentStorageError("S3_BUCKET is required for S3 document storage")
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def put(self, key: str, content: bytes) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=str(_validate_key(key)), Body=content
            )
        except (BotoCoreError, ClientError) as error:
            raise DocumentStorageError(
                "Could not store the uploaded document in S3"
            ) from error

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(
                Bucket=self.bucket, Key=str(_validate_key(key))
            )
            return response["Body"].read()
        except (BotoCoreError, ClientError, KeyError) as error:
            raise DocumentStorageError(
                "Could not read the stored document from S3"
            ) from error

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=str(_validate_key(key)))
        except (BotoCoreError, ClientError) as error:
            raise DocumentStorageError(
                "Could not delete the stored document from S3"
            ) from error


def get_document_storage() -> DocumentStorage:
    if settings.document_storage_backend == "local":
        return LocalDocumentStorage(settings.local_document_storage_path)
    if settings.document_storage_backend == "s3":
        return S3DocumentStorage()
    raise DocumentStorageError("Unsupported document storage backend")
