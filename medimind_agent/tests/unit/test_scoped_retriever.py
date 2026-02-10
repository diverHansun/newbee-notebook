import json

from medimind_agent.core.common.node_utils import extract_document_id
from medimind_agent.core.rag.retrieval.scoped_retriever import ScopedRetriever
from llama_index.core.schema import TextNode, NodeWithScore


class _DummyRetriever:
    def __init__(self, results):
        self._results = results

    def retrieve(self, _query_bundle):
        return self._results

    async def aretrieve(self, _query_bundle):
        return self._results


def _make_result(doc_id: str):
    metadata = {
        "_node_content": json.dumps({"metadata": {"document_id": doc_id}})
    }
    node = TextNode(text=f"text-{doc_id}", metadata=metadata)
    return NodeWithScore(node=node, score=1.0)


def test_scoped_retriever_filters_out_of_scope_results():
    results = [
        _make_result("doc-a"),
        _make_result("doc-b"),
        _make_result("doc-a"),
    ]
    retriever = ScopedRetriever(
        base_retriever=_DummyRetriever(results),
        allowed_doc_ids=["doc-a"],
        top_k=10,
    )

    scoped = retriever.retrieve("query")
    assert len(scoped) >= 1
    assert {extract_document_id(item) for item in scoped} == {"doc-a"}


def test_scoped_retriever_supports_empty_scope():
    results = [_make_result("doc-a"), _make_result("doc-b")]
    retriever = ScopedRetriever(
        base_retriever=_DummyRetriever(results),
        allowed_doc_ids=[],
        top_k=10,
    )

    scoped = retriever.retrieve("query")
    assert scoped == []
