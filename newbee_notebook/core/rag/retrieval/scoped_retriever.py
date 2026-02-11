"""Retriever wrapper that enforces notebook document scope."""

from __future__ import annotations

from typing import Iterable, List, Optional

from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle

from newbee_notebook.core.common.node_utils import extract_document_id


class ScopedRetriever(BaseRetriever):
    """Wrap an existing retriever and filter results by allowed document IDs."""

    def __init__(
        self,
        base_retriever: BaseRetriever,
        allowed_doc_ids: Optional[Iterable[str]] = None,
        top_k: Optional[int] = None,
    ):
        super().__init__()
        self._base_retriever = base_retriever
        self._allowed_doc_ids = (
            None if allowed_doc_ids is None else set(allowed_doc_ids)
        )
        self._top_k = top_k

    def _apply_scope(self, results: List[NodeWithScore]) -> List[NodeWithScore]:
        scoped = results
        if self._allowed_doc_ids is not None:
            scoped = [
                result
                for result in results
                if extract_document_id(result) in self._allowed_doc_ids
            ]
        if self._top_k is not None:
            return scoped[: self._top_k]
        return scoped

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        return self._apply_scope(self._base_retriever.retrieve(query_bundle))

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        base_aretrieve = getattr(self._base_retriever, "aretrieve", None)
        if callable(base_aretrieve):
            results = await base_aretrieve(query_bundle)
        else:
            results = self._base_retriever.retrieve(query_bundle)
        return self._apply_scope(results)
