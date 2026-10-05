import hashlib
import logging
from pathlib import PurePosixPath
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.permissions import require_membership
from app.core.security import get_current_user
from app.features.documents import processing_service
from app.features.documents.answer_generation import (
    ABSTENTION_MESSAGE,
    AnswerGenerationError,
    generate_grounded_answer,
)
from app.features.documents.embeddings import EmbeddingError, embed_texts
from app.features.documents.models import Document, DocumentChunk, DocumentStatus
from app.features.documents.processing import (
    SUPPORTED_TYPES,
    DocumentProcessingError,
    normalize_document_text,
)
from app.features.documents.reranking import RerankingError, rerank_texts
from app.features.documents.schemas import (
    AnswerRequest,
    AnswerResponse,
    DocumentCreate,
    DocumentDetail,
    DocumentPublic,
    RetrievalResponse,
    SearchResponse,
    SearchResult,
    VectorIndexResponse,
)
from app.features.documents.storage import DocumentStorageError, get_document_storage
from app.features.documents.tasks import enqueue_document_processing
from app.features.organization_memberships.models import MembershipRole
from app.features.users.models import User

router = APIRouter(prefix="/organizations/{organization_id}", tags=["Documents"])
CHUNK_SIZE = processing_service.CHUNK_SIZE
CHUNK_OVERLAP = processing_service.CHUNK_OVERLAP
_split_content = processing_service.split_content


logger = logging.getLogger(__name__)


def _create_document(
    *,
    organization_id: UUID,
    current_user: User,
    db: Session,
    title: str,
    source_name: str,
    content_type_hint: str | None,
    raw_content: bytes,
) -> Document:
    content_hash = hashlib.sha256(raw_content).hexdigest()
    duplicate = db.execute(
        select(Document.id).where(
            Document.organization_id == organization_id,
            Document.content_hash == content_hash,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document content already exists in the organization",
        )

    prior_version = db.execute(
        select(Document)
        .where(
            Document.organization_id == organization_id,
            Document.source_name == source_name,
        )
        .order_by(Document.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    group_id = prior_version.version_group_id if prior_version else uuid4()
    version_number = prior_version.version_number + 1 if prior_version else 1
    document_id = uuid4()
    storage_key = f"organizations/{organization_id}/documents/{document_id}/source"
    try:
        get_document_storage().put(storage_key, raw_content)
    except DocumentStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    document = Document(
        id=document_id,
        organization_id=organization_id,
        uploaded_by_id=current_user.id,
        version_group_id=group_id,
        version_number=version_number,
        title=title,
        source_name=source_name,
        content_type=content_type_hint or "application/octet-stream",
        content_hash=content_hash,
        storage_key=storage_key,
        raw_content=None,
        content="",
        processing_status=DocumentStatus.PENDING,
    )
    db.add(document)
    try:
        db.commit()
        db.refresh(document)
    except IntegrityError:
        db.rollback()
        try:
            get_document_storage().delete(storage_key)
        except DocumentStorageError:
            logger.exception(
                "Could not clean up failed document upload %s", document_id
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A document with this content or version already exists",
        ) from None

    try:
        enqueue_document_processing(document.id)
    except Exception as error:
        logger.exception("Could not enqueue document processing for %s", document.id)
        document.processing_status = DocumentStatus.FAILED
        document.processing_error = "Document processing could not be queued"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Document was stored but processing could not be queued; retry it later"
            ),
        ) from error
    db.refresh(document)
    return document


@router.post(
    "/documents", response_model=DocumentPublic, status_code=status.HTTP_201_CREATED
)
def ingest_text_document(
    organization_id: UUID,
    payload: DocumentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Document:
    membership = require_membership(organization_id, current_user, db)
    if membership.role == MembershipRole.VIEWER:
        raise HTTPException(
            status_code=403, detail="Viewer role cannot ingest documents"
        )
    if payload.content_type.lower() not in {"text/plain", "text/markdown"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Text endpoint supports text/plain and text/markdown only",
        )
    try:
        normalized = normalize_document_text(payload.content)
    except DocumentProcessingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _create_document(
        organization_id=organization_id,
        current_user=current_user,
        db=db,
        title=payload.title,
        source_name=payload.source_name,
        content_type_hint=payload.content_type.lower(),
        raw_content=normalized.encode("utf-8"),
    )


@router.post(
    "/documents/upload",
    response_model=DocumentPublic,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=255)] = None,
) -> Document:
    membership = require_membership(organization_id, current_user, db)
    if membership.role == MembershipRole.VIEWER:
        raise HTTPException(
            status_code=403, detail="Viewer role cannot ingest documents"
        )
    if not file.filename:
        raise HTTPException(status_code=422, detail="A filename is required")
    source_name = file.filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not source_name or len(source_name) > 255:
        raise HTTPException(status_code=422, detail="Filename must be 1-255 characters")
    if PurePosixPath(source_name).suffix.lower() not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Unsupported file type; use .txt, .md, .html, .pdf, .docx, "
                ".png, .jpg, .jpeg, .tif, or .tiff"
            ),
        )
    raw_content = file.file.read(settings.max_document_size_bytes + 1)
    if not raw_content:
        raise HTTPException(status_code=422, detail="Uploaded file cannot be empty")
    if len(raw_content) > settings.max_document_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Document exceeds the {settings.max_document_size_bytes}-byte "
                "upload limit"
            ),
        )
    resolved_title = (
        title.strip() if title and title.strip() else PurePosixPath(source_name).stem
    )
    if not resolved_title:
        raise HTTPException(status_code=422, detail="A document title is required")
    return _create_document(
        organization_id=organization_id,
        current_user=current_user,
        db=db,
        title=resolved_title,
        source_name=source_name,
        content_type_hint=file.content_type,
        raw_content=raw_content,
    )


@router.get("/documents", response_model=list[DocumentPublic])
def list_documents(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Document]:
    require_membership(organization_id, current_user, db)
    return list(
        db.scalars(
            select(Document)
            .where(Document.organization_id == organization_id)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    organization_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Document:
    require_membership(organization_id, current_user, db)
    document = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/documents/{document_id}/versions", response_model=list[DocumentPublic])
def list_document_versions(
    organization_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Document]:
    require_membership(organization_id, current_user, db)
    document = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return list(
        db.scalars(
            select(Document)
            .where(Document.version_group_id == document.version_group_id)
            .order_by(Document.version_number.desc())
        )
    )


@router.post("/documents/{document_id}/retry", response_model=DocumentPublic)
def retry_document_processing(
    organization_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Document:
    membership = require_membership(organization_id, current_user, db)
    if membership.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise HTTPException(
            status_code=403, detail="Organization administrator role required"
        )
    document = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.processing_status != DocumentStatus.FAILED:
        raise HTTPException(
            status_code=409, detail="Only failed documents can be retried"
        )
    if document.storage_key is None and document.raw_content is None:
        raise HTTPException(
            status_code=409, detail="The original document content is unavailable"
        )

    document.processing_status = DocumentStatus.PENDING
    document.processing_error = None
    db.commit()
    try:
        enqueue_document_processing(document.id)
    except Exception as error:
        logger.exception("Could not enqueue document retry for %s", document.id)
        document.processing_status = DocumentStatus.FAILED
        document.processing_error = "Document processing could not be queued"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retry could not be queued; try again later",
        ) from error
    db.refresh(document)
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    organization_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    membership = require_membership(organization_id, current_user, db)
    if membership.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise HTTPException(
            status_code=403, detail="Organization administrator role required"
        )
    document = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    storage_key = document.storage_key
    db.delete(document)
    db.commit()
    if storage_key is not None:
        try:
            get_document_storage().delete(storage_key)
        except DocumentStorageError as error:
            logger.exception("Could not remove stored document %s", document_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Document was deleted from the database but stored-file "
                    "cleanup failed"
                ),
            ) from error


def _retrieve_results(
    organization_id: UUID,
    query: str,
    db: Session,
    limit: int,
) -> list[SearchResult]:
    terms = [term for term in query.split() if term]
    if not terms:
        raise HTTPException(status_code=422, detail="Search query must contain text")
    escaped_terms = [
        term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        for term in terms
    ]
    predicates = [
        DocumentChunk.content.ilike(f"%{term}%", escape="\\") for term in escaped_terms
    ]
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.organization_id == organization_id,
            Document.processing_status == DocumentStatus.READY,
            and_(*predicates),
        )
        .limit(500)
    ).all()

    normalized_terms = [term.casefold() for term in terms]
    ranked: list[tuple[int, DocumentChunk, Document, str]] = []
    for chunk, document in rows:
        folded = chunk.content.casefold()
        score = sum(folded.count(term) for term in normalized_terms)
        first_position = min(
            (folded.find(term) for term in normalized_terms if term in folded),
            default=0,
        )
        excerpt_start = max(0, first_position - 100)
        excerpt = chunk.content[excerpt_start : excerpt_start + 300]
        ranked.append((score, chunk, document, excerpt))

    ranked.sort(
        key=lambda item: (
            -item[0],
            item[2].title.casefold(),
            item[1].chunk_index,
            str(item[1].id),
        )
    )
    return [
        SearchResult(
            citation_id=f"[{index}]",
            document_id=document.id,
            version_group_id=document.version_group_id,
            version_number=document.version_number,
            chunk_id=chunk.id,
            title=document.title,
            source_name=document.source_name,
            chunk_index=chunk.chunk_index,
            excerpt=excerpt,
            score=score,
        )
        for index, (score, chunk, document, excerpt) in enumerate(
            ranked[:limit], start=1
        )
    ]


@router.post("/vector-index/rebuild", response_model=VectorIndexResponse)
def rebuild_vector_index(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> VectorIndexResponse:
    membership = require_membership(organization_id, current_user, db)
    if membership.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise HTTPException(
            status_code=403, detail="Organization administrator role required"
        )
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.organization_id == organization_id,
                Document.processing_status == DocumentStatus.READY,
            )
            .order_by(DocumentChunk.id)
        )
    )
    try:
        for start in range(0, len(chunks), 128):
            batch = chunks[start : start + 128]
            vectors = embed_texts([chunk.content for chunk in batch])
            if len(vectors) != len(batch):
                raise EmbeddingError(
                    "Embedding model returned an incomplete vector batch"
                )
            for chunk, vector in zip(batch, vectors, strict=True):
                chunk.embedding = vector
                chunk.embedding_model = settings.embedding_model_name
        db.commit()
    except EmbeddingError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return VectorIndexResponse(
        indexed_chunks=len(chunks),
        model_name=settings.embedding_model_name,
    )


def _semantic_retrieve_results(
    organization_id: UUID,
    query: str,
    db: Session,
    limit: int,
) -> list[SearchResult]:
    if not query.strip():
        raise HTTPException(status_code=422, detail="Search query must contain text")
    try:
        vectors = embed_texts([query.strip()])
        if len(vectors) != 1 or not vectors[0]:
            raise EmbeddingError("Embedding model returned an invalid query vector")
        query_vector = vectors[0]
    except EmbeddingError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.organization_id == organization_id,
            Document.processing_status == DocumentStatus.READY,
            DocumentChunk.embedding_model == settings.embedding_model_name,
            DocumentChunk.embedding.is_not(None),
        )
    ).all()
    ranked: list[tuple[float, DocumentChunk, Document]] = []
    for chunk, document in rows:
        vector = chunk.embedding
        if len(vector) != len(query_vector):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Stored document vector dimensions do not match "
                    "the configured model"
                ),
            )
        similarity = sum(
            left * right for left, right in zip(query_vector, vector, strict=True)
        )
        ranked.append((similarity, chunk, document))
    ranked.sort(
        key=lambda item: (
            -item[0],
            item[2].title.casefold(),
            item[1].chunk_index,
            str(item[1].id),
        )
    )
    return [
        SearchResult(
            citation_id=f"[{index}]",
            document_id=document.id,
            version_group_id=document.version_group_id,
            version_number=document.version_number,
            chunk_id=chunk.id,
            title=document.title,
            source_name=document.source_name,
            chunk_index=chunk.chunk_index,
            excerpt=chunk.content[:300],
            score=similarity,
        )
        for index, (similarity, chunk, document) in enumerate(ranked[:limit], start=1)
    ]


@router.get("/vector-search", response_model=SearchResponse)
def vector_search_documents(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> SearchResponse:
    require_membership(organization_id, current_user, db)
    return SearchResponse(
        query=q,
        results=_semantic_retrieve_results(organization_id, q, db, limit),
    )


@router.get("/hybrid-search", response_model=SearchResponse)
def hybrid_search_documents(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> SearchResponse:
    require_membership(organization_id, current_user, db)
    return SearchResponse(
        query=q,
        results=_hybrid_retrieve_results(organization_id, q, db, limit),
    )


def _hybrid_retrieve_results(
    organization_id: UUID,
    query: str,
    db: Session,
    limit: int,
) -> list[SearchResult]:
    candidate_limit = 50
    keyword_results = _retrieve_results(organization_id, query, db, candidate_limit)
    semantic_results = _semantic_retrieve_results(
        organization_id, query, db, candidate_limit
    )

    # Reciprocal rank fusion combines independently ranked keyword and semantic hits.
    rank_constant = 60
    fused: dict[UUID, tuple[SearchResult, float]] = {}
    for results in (keyword_results, semantic_results):
        for rank, result in enumerate(results, start=1):
            previous = fused.get(result.chunk_id)
            score = 1 / (rank_constant + rank)
            fused[result.chunk_id] = (
                result,
                score + (previous[1] if previous else 0.0),
            )

    ordered = sorted(
        fused.values(),
        key=lambda item: (
            -item[1],
            item[0].title.casefold(),
            item[0].chunk_index,
            str(item[0].chunk_id),
        ),
    )

    candidates = [result for result, _ in ordered]
    try:
        reranker_scores = rerank_texts(query, [result.excerpt for result in candidates])
    except RerankingError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    if len(reranker_scores) != len(candidates):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reranker returned an incomplete score batch",
        )
    reranked = sorted(
        zip(candidates, reranker_scores, strict=True),
        key=lambda item: (
            -item[1],
            item[0].title.casefold(),
            item[0].chunk_index,
            str(item[0].chunk_id),
        ),
    )[:limit]
    return [
        result.model_copy(update={"citation_id": f"[{index}]", "score": score})
        for index, (result, score) in enumerate(reranked, start=1)
    ]


@router.get("/search", response_model=SearchResponse)
def search_documents(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> SearchResponse:
    require_membership(organization_id, current_user, db)
    return SearchResponse(
        query=q,
        results=_retrieve_results(organization_id, q, db, limit),
    )


@router.get("/retrieve", response_model=RetrievalResponse)
def retrieve_citations(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
) -> RetrievalResponse:
    require_membership(organization_id, current_user, db)
    return RetrievalResponse(
        query=q,
        citations=_retrieve_results(organization_id, q, db, limit),
    )


@router.post("/answer", response_model=AnswerResponse)
def answer_question(
    organization_id: UUID,
    payload: AnswerRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnswerResponse:
    require_membership(organization_id, current_user, db)
    citations = _hybrid_retrieve_results(
        organization_id, payload.question, db, payload.limit
    )
    if not citations:
        return AnswerResponse(
            question=payload.question,
            answer=ABSTENTION_MESSAGE,
            citations=[],
            abstained=True,
        )

    try:
        generated = generate_grounded_answer(payload.question, citations)
    except AnswerGenerationError as error:
        logger.exception(
            "Could not generate an answer for organization %s", organization_id
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    cited_results = [
        citation
        for citation in citations
        if citation.citation_id in generated.citation_ids
    ]
    return AnswerResponse(
        question=payload.question,
        answer=generated.answer,
        citations=cited_results,
        abstained=generated.abstained,
    )
