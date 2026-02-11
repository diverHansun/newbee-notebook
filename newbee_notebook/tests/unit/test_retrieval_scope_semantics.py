from newbee_notebook.core.rag.retrieval.filters import build_document_filters
from newbee_notebook.core.rag.retrieval.hybrid_retriever import HybridRetriever


class _DummyRetriever:
    def __init__(self, results):
        self._results = results

    def retrieve(self, _query_bundle):
        return self._results

    async def aretrieve(self, _query_bundle):
        return self._results


def test_build_document_filters_keeps_empty_scope():
    pg_filters, es_filters, allowed_doc_ids = build_document_filters([])
    assert pg_filters is None
    assert es_filters is None
    assert allowed_doc_ids == []


def test_hybrid_retriever_empty_scope_returns_no_results():
    retriever = HybridRetriever(
        pgvector_retriever=_DummyRetriever([]),
        es_retriever=_DummyRetriever([]),
        allowed_doc_ids=[],
    )
    assert retriever.retrieve("test") == []

