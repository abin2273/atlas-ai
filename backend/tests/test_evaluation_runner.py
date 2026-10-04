import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from app.evaluation.runner import (
    EvaluationDataset,
    evaluate_dataset,
    load_dataset,
    retrieval_metrics,
)
from pydantic import ValidationError

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
DOC_A = UUID("00000000-0000-0000-0000-000000000101")
DOC_B = UUID("00000000-0000-0000-0000-000000000102")
DOC_OUTSIDE_GOLD = UUID("00000000-0000-0000-0000-000000000199")


def test_retrieval_metrics_calculate_recall_mrr_and_ndcg() -> None:
    metrics = retrieval_metrics([DOC_B, DOC_A], [DOC_A], k=2)
    assert metrics.recall_at_k == 1.0
    assert metrics.reciprocal_rank_at_k == 0.5
    assert metrics.ndcg_at_k == pytest.approx(1 / 1.584962500721156)

    misses = retrieval_metrics([DOC_OUTSIDE_GOLD], [DOC_A], k=1)
    assert misses.recall_at_k == misses.reciprocal_rank_at_k == misses.ndcg_at_k == 0
    deduplicated = retrieval_metrics([DOC_B, DOC_B, DOC_A], [DOC_A], k=2)
    assert deduplicated.reciprocal_rank_at_k == 0.5


def test_dataset_requires_relevant_documents_or_expected_abstention() -> None:
    with pytest.raises(ValidationError, match="Answerable cases must declare"):
        EvaluationDataset.model_validate(
            {
                "cases": [
                    {
                        "organization_id": str(ORG_ID),
                        "question": "What is documented?",
                    }
                ]
            }
        )
    with pytest.raises(ValidationError, match="cannot declare relevant"):
        EvaluationDataset.model_validate(
            {
                "cases": [
                    {
                        "organization_id": str(ORG_ID),
                        "question": "What is documented?",
                        "relevant_document_ids": [str(DOC_A)],
                        "should_abstain": True,
                    }
                ]
            }
        )


def test_evaluation_runner_scores_retrieval_citations_and_abstention() -> None:
    dataset = EvaluationDataset.model_validate(
        {
            "cases": [
                {
                    "organization_id": str(ORG_ID),
                    "question": "What is documented?",
                    "relevant_document_ids": [str(DOC_A)],
                },
                {
                    "organization_id": str(ORG_ID),
                    "question": "What is on Mars?",
                    "should_abstain": True,
                },
            ]
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/hybrid-search"):
            payload = (
                {"results": [{"document_id": str(DOC_B)}, {"document_id": str(DOC_A)}]}
                if "What is documented?" in request.url.params["q"]
                else {"results": []}
            )
        else:
            payload = (
                {
                    "abstained": False,
                    "citations": [{"document_id": str(DOC_A)}],
                    "answer": "The policy states the rule [1].",
                }
                if request.read() and b"documented" in request.content
                else {
                    "abstained": True,
                    "citations": [],
                    "answer": "Not enough evidence.",
                }
            )
        return httpx.Response(200, json=payload)

    client = httpx.Client(
        base_url="http://atlas.test",
        headers={"Authorization": "Bearer evaluation-token"},
        transport=httpx.MockTransport(handler),
    )
    result = evaluate_dataset(
        dataset, base_url="http://atlas.test", token="unused", k=2, client=client
    )

    assert result["retrieval_case_count"] == 1
    assert result["recall_at_k"] == 1.0
    assert result["mrr_at_k"] == 0.5
    assert result["abstention_accuracy"] == 1.0
    assert result["citation_precision"] == 1.0
    assert result["citation_recall"] == 1.0
    assert result["unsupported_citation_count"] == 0
    assert result["cases"] == 2
    client.close()


def test_evaluation_reports_unsupported_citations() -> None:
    dataset = EvaluationDataset.model_validate(
        {
            "cases": [
                {
                    "organization_id": str(ORG_ID),
                    "question": "What is documented?",
                    "relevant_document_ids": [str(DOC_A)],
                }
            ]
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/hybrid-search"):
            payload = {"results": [{"document_id": str(DOC_A)}]}
        else:
            payload = {
                "abstained": False,
                "citations": [{"document_id": str(DOC_OUTSIDE_GOLD)}],
                "answer": "Unsupported claim [1].",
            }
        return httpx.Response(200, json=payload)

    with httpx.Client(
        base_url="http://atlas.test", transport=httpx.MockTransport(handler)
    ) as client:
        result = evaluate_dataset(
            dataset, base_url="http://atlas.test", token="unused", client=client
        )
    assert result["citation_precision"] == 0.0
    assert result["citation_recall"] == 0.0
    assert result["unsupported_citation_count"] == 1


def test_load_dataset_reads_json_and_rejects_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "organization_id": str(ORG_ID),
                        "question": "What is documented?",
                        "relevant_document_ids": [str(DOC_A)],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert len(load_dataset(path).cases) == 1
    with pytest.raises(ValueError, match="Could not read evaluation dataset"):
        load_dataset(tmp_path / "missing.json")


def test_evaluation_propagates_api_errors() -> None:
    dataset = EvaluationDataset.model_validate(
        {
            "cases": [
                {
                    "organization_id": str(ORG_ID),
                    "question": "What is documented?",
                    "relevant_document_ids": [str(DOC_A)],
                }
            ]
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "retrieval unavailable"})

    with (
        httpx.Client(
            base_url="http://atlas.test", transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        evaluate_dataset(
            dataset, base_url="http://atlas.test", token="unused", client=client
        )
