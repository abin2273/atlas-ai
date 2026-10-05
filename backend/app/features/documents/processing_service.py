from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.features.documents.embeddings import EmbeddingError, embed_texts
from app.features.documents.models import Document, DocumentChunk, DocumentStatus
from app.features.documents.processing import (
    DocumentProcessingError,
    extract_document_text,
)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150


def split_content(content: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(start + CHUNK_SIZE, len(content))
        if end < len(content):
            boundary = content.rfind(" ", start + CHUNK_SIZE // 2, end)
            if boundary > start:
                end = boundary
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(content):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def process_document_content(
    document: Document,
    raw_content: bytes,
    db: Session,
) -> None:
    document.processing_status = DocumentStatus.PROCESSING
    document.processing_error = None
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    try:
        content_type, extracted, extracted_metadata = extract_document_text(
            document.source_name,
            raw_content,
            document.content_type,
        )
        document.content_type = content_type
        document.content = extracted
        document.extracted_metadata = extracted_metadata
        chunks = split_content(extracted)
        embeddings = embed_texts(chunks)
        if len(embeddings) != len(chunks):
            raise EmbeddingError("Embedding model returned an incomplete vector batch")
        for index, (chunk, embedding) in enumerate(
            zip(chunks, embeddings, strict=True)
        ):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=embedding,
                    embedding_model=settings.embedding_model_name,
                )
            )
        document.processing_status = DocumentStatus.READY
    except (DocumentProcessingError, EmbeddingError) as error:
        document.content = ""
        document.extracted_metadata = {}
        document.processing_status = DocumentStatus.FAILED
        document.processing_error = str(error)
    db.commit()
    db.refresh(document)
