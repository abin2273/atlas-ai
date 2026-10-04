import argparse
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class EvaluationCase(BaseModel):
    organization_id: UUID
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2)]
    reference_answer: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
        ]
        | None
    ) = None
    relevant_document_ids: list[UUID] = Field(default_factory=list)
    should_abstain: bool = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_expected_behavior(self) -> "EvaluationCase":
        if self.should_abstain and self.relevant_document_ids:
            raise ValueError("Abstention cases cannot declare relevant document IDs")
        if not self.should_abstain and not self.relevant_document_ids:
            raise ValueError(
                "Answerable cases must declare at least one relevant document ID"
            )
        if len(set(self.relevant_document_ids)) != len(self.relevant_document_ids):
            raise ValueError("Relevant document IDs must be unique")
        return self


class EvaluationDataset(BaseModel):
    cases: list[EvaluationCase] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class RetrievalMetrics:
    recall_at_k: float
    reciprocal_rank_at_k: float
    ndcg_at_k: float


def retrieval_metrics(
    retrieved_ids: list[UUID], relevant_ids: list[UUID], k: int
) -> RetrievalMetrics:
    if k < 1:
        raise ValueError("k must be at least 1")
    if not relevant_ids:
        raise ValueError("relevant_ids must not be empty")
    ranked = list(dict.fromkeys(retrieved_ids))[:k]
    relevant = set(relevant_ids)
    hits = [
        index
        for index, document_id in enumerate(ranked, start=1)
        if document_id in relevant
    ]
    recall = len({ranked[index - 1] for index in hits}) / len(relevant)
    reciprocal_rank = 1 / hits[0] if hits else 0.0
    dcg = sum(1 / math.log2(rank + 1) for rank in hits)
    ideal_hits = min(len(relevant), k)
    ideal_dcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return RetrievalMetrics(
        recall_at_k=recall,
        reciprocal_rank_at_k=reciprocal_rank,
        ndcg_at_k=dcg / ideal_dcg if ideal_dcg else 0.0,
    )


def load_dataset(path: Path) -> EvaluationDataset:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Could not read evaluation dataset {path}: {error}"
        ) from error
    return EvaluationDataset.model_validate(payload)


def evaluate_dataset(
    dataset: EvaluationDataset,
    *,
    base_url: str,
    token: str,
    k: int = 10,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    if not 1 <= k <= 50:
        raise ValueError("k must be between 1 and 50")
    owns_client = client is None
    http = client or httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=180,
    )
    per_case: list[dict[str, object]] = []
    retrieval_scores: list[RetrievalMetrics] = []
    abstention_correct = 0
    answerable_cases = 0
    citation_precisions: list[float] = []
    citation_recalls: list[float] = []
    unsupported_citations = 0
    unsupported_answers = 0
    total_citations = 0

    try:
        for index, case in enumerate(dataset.cases, start=1):
            prefix = f"/api/v1/organizations/{case.organization_id}"
            search_response = http.get(
                f"{prefix}/hybrid-search",
                params={"q": case.question, "limit": 50},
            )
            search_response.raise_for_status()
            search_payload = search_response.json()
            retrieved_ids = list(
                dict.fromkeys(
                    UUID(result["document_id"]) for result in search_payload["results"]
                )
            )[:k]

            answer_response = http.post(
                f"{prefix}/answer",
                json={"question": case.question, "limit": k},
            )
            answer_response.raise_for_status()
            answer_payload = answer_response.json()
            cited_ids = list(
                dict.fromkeys(
                    UUID(citation["document_id"])
                    for citation in answer_payload["citations"]
                )
            )
            abstained = answer_payload["abstained"]
            correct_abstention = abstained is case.should_abstain
            abstention_correct += int(correct_abstention)
            total_citations += len(set(cited_ids))
            if not case.should_abstain:
                answerable_cases += 1
                relevant = set(case.relevant_document_ids)
                cited = set(cited_ids)
                citation_precisions.append(
                    len(cited & relevant) / len(cited) if cited else 0.0
                )
                citation_recalls.append(len(cited & relevant) / len(relevant))
                unsupported_citations += len(cited - relevant)
                unsupported_answers += int(bool(cited - relevant))
                metrics = retrieval_metrics(
                    retrieved_ids, case.relevant_document_ids, k
                )
                retrieval_scores.append(metrics)
                metric_data: dict[str, object] = asdict(metrics)
            else:
                unsupported_citations += len(set(cited_ids))
                unsupported_answers += int(not abstained)
                metric_data = {}
            per_case.append(
                {
                    "case": index,
                    "question": case.question,
                    "reference_answer": case.reference_answer,
                    "answer": answer_payload["answer"],
                    "retrieved_document_ids": [str(value) for value in retrieved_ids],
                    "cited_document_ids": [str(value) for value in cited_ids],
                    "expected_abstention": case.should_abstain,
                    "actual_abstention": abstained,
                    "abstention_correct": correct_abstention,
                    **metric_data,
                }
            )
    finally:
        if owns_client:
            http.close()

    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    return {
        "cases": len(dataset.cases),
        "k": k,
        "retrieval_case_count": len(retrieval_scores),
        "recall_at_k": mean([item.recall_at_k for item in retrieval_scores]),
        "mrr_at_k": mean([item.reciprocal_rank_at_k for item in retrieval_scores]),
        "ndcg_at_k": mean([item.ndcg_at_k for item in retrieval_scores]),
        "abstention_accuracy": abstention_correct / len(dataset.cases),
        "answerable_case_count": answerable_cases,
        "citation_precision": mean(citation_precisions),
        "citation_recall": mean(citation_recalls),
        "unsupported_citation_count": unsupported_citations,
        "unsupported_answer_count": unsupported_answers,
        "citation_count": total_citations,
        "per_case": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate AtlasAI hybrid retrieval and grounded answers."
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument(
        "--base-url", default=os.getenv("ATLAS_API_URL", "http://localhost:8000")
    )
    parser.add_argument("--token", default=os.getenv("ATLAS_EVAL_TOKEN"))
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    if not args.token:
        parser.error("provide --token or set ATLAS_EVAL_TOKEN")
    result = evaluate_dataset(
        load_dataset(args.dataset),
        base_url=args.base_url,
        token=args.token,
        k=args.k,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
