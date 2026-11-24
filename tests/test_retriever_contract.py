import asyncio

import pytest

from backend.domain.models import SearchHit
from backend.domain.testing import FakeRetriever
from backend.services.retrieval import RetrievalService


HITS = [
    SearchHit("first", 0.9, "docs"),
    SearchHit("second", 0.8, "docs"),
    SearchHit("other", 0.7, "other"),
]


class ContractVectorStore:
    def search(self, query, *, namespace, top_k, filter_expression=None):
        return [hit for hit in HITS if hit.namespace == namespace][:top_k]


def fake_retriever():
    return FakeRetriever(HITS)


def real_retrieval_service():
    return RetrievalService(ContractVectorStore(), similarity_threshold=0.0)


@pytest.mark.parametrize("factory", [fake_retriever, real_retrieval_service])
def test_async_retriever_contract_preserves_namespace_top_k_and_order(factory):
    retriever = factory()

    results = asyncio.run(retriever.search("query", namespace="docs", top_k=1))

    assert results == [HITS[0]]
    assert asyncio.run(retriever.search("query", namespace="missing")) == []
