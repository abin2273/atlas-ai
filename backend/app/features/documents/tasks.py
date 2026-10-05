import logging
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.features.documents.models import Document, DocumentStatus
from app.features.documents.processing_service import process_document_content
from app.features.documents.storage import DocumentStorageError, get_document_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="documents.process")
def process_document_task(document_id: str) -> str:
    parsed_id = UUID(document_id)
    with SessionLocal() as db:
        document = db.execute(
            select(Document).where(Document.id == parsed_id)
        ).scalar_one_or_none()
        if document is None:
            logger.warning(
                "Document processing task references missing document %s", document_id
            )
            return "missing"
        document.processing_status = DocumentStatus.PROCESSING
        document.processing_error = None
        db.commit()
        try:
            if document.storage_key:
                raw_content = get_document_storage().get(document.storage_key)
            elif document.raw_content is not None:
                raw_content = document.raw_content
            else:
                raise DocumentStorageError(
                    "The original document content is unavailable"
                )
            process_document_content(document, raw_content, db)
        except Exception as error:
            logger.exception("Document processing failed for %s", document_id)
            db.rollback()
            failed = db.execute(
                select(Document).where(Document.id == parsed_id)
            ).scalar_one_or_none()
            if failed is not None:
                failed.processing_status = DocumentStatus.FAILED
                failed.processing_error = str(error)[:2000]
                failed.content = ""
                db.commit()
            raise
        return document.processing_status.value


def enqueue_document_processing(document_id: UUID) -> None:
    process_document_task.delay(str(document_id))
