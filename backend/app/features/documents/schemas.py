from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.features.documents.models import DocumentStatus


class DocumentCreate(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    source_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    content_type: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=100)
    ] = "text/plain"
    content: Annotated[str, StringConstraints(min_length=1, max_length=1_000_000)]


class DocumentPublic(BaseModel):
    id: UUID
    organization_id: UUID
    uploaded_by_id: UUID | None
    version_group_id: UUID
    version_number: int
    title: str
    source_name: str
    content_type: str
    content_hash: str
    extracted_metadata: dict[str, str | int]
    processing_status: DocumentStatus
    processing_error: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(DocumentPublic):
    content: str


class SearchResult(BaseModel):
    citation_id: str
    document_id: UUID
    version_group_id: UUID
    version_number: int
    chunk_id: UUID
    title: str
    source_name: str
    chunk_index: int
    excerpt: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class RetrievalResponse(BaseModel):
    query: str
    citations: list[SearchResult]


class AnswerRequest(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=2000)
    ]
    limit: Annotated[int, Field(ge=1, le=20)] = 8


class AnswerResponse(BaseModel):
    question: str
    answer: str
    citations: list[SearchResult]
    abstained: bool


class VectorIndexResponse(BaseModel):
    indexed_chunks: int
    model_name: str
