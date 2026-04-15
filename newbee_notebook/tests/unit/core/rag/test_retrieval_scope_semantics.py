from newbee_notebook.core.rag.retrieval.filters import build_document_filters
from newbee_notebook.core.rag.retrieval.hybrid_retriever import HybridRetriever
from llama_index.core.vector_stores import FilterOperator


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


def test_build_document_filters_uses_stable_source_document_id_for_single_doc_scope():
    pg_filters, es_filters, allowed_doc_ids = build_document_filters(["doc-1"])

    assert allowed_doc_ids == ["doc-1"]
    assert pg_filters is not None
    assert es_filters is not None
    assert pg_filters.filters[0].key == "source_document_id"
    assert pg_filters.filters[0].operator == FilterOperator.EQ
    assert pg_filters.filters[0].value == "doc-1"
    assert es_filters.filters[0].key == "source_document_id"
    assert es_filters.filters[0].operator == FilterOperator.EQ
    assert es_filters.filters[0].value == "doc-1"


def test_hybrid_retriever_empty_scope_returns_no_results():
    retriever = HybridRetriever(
        pgvector_retriever=_DummyRetriever([]),
        es_retriever=_DummyRetriever([]),
        allowed_doc_ids=[],
    )
    assert retriever.retrieve("test") == []

