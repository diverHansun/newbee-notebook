"""Conclude mode implementation using CondensePlusContextChatEngine."""

from typing import Optional

from llama_index.core import VectorStoreIndex
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.chat_engine.types import BaseChatEngine
from llama_index.core.llms import LLM
from llama_index.core.memory import BaseMemory

from newbee_notebook.core.common.config import get_conclude_skip_condense
from newbee_notebook.core.common.node_utils import extract_document_id
from newbee_notebook.core.engine.modes.base import BaseMode, ModeConfig, ModeType
from newbee_notebook.core.prompts import load_prompt
from newbee_notebook.core.rag.retrieval import build_hybrid_retriever
from newbee_notebook.core.rag.retrieval.filters import build_document_filters
from newbee_notebook.core.rag.retrieval.scoped_retriever import ScopedRetriever

DEFAULT_CONCLUDE_SYSTEM_PROMPT = load_prompt("conclude.md")
DEFAULT_CONCLUDE_CONTEXT_PROMPT = (
    "The following context is retrieved from notebook documents.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Please produce a concise but complete conclusion according to the user's request. "
    "Extract key points, structure them clearly, and call out assumptions if context is incomplete."
)


class ConcludeMode(BaseMode):
    """Conclude mode using ChatEngine for lightweight multi-turn summarization."""

    def __init__(
        self,
        llm: LLM,
        index: Optional[VectorStoreIndex] = None,
        es_index: Optional[VectorStoreIndex] = None,
        memory: Optional[BaseMemory] = None,
        config: Optional[ModeConfig] = None,
        similarity_top_k: int = 8,
    ):
        super().__init__(llm=llm, memory=memory, config=config)
        self._index = index
        self._es_index = es_index
        self._similarity_top_k = similarity_top_k
        self._chat_engine: Optional[BaseChatEngine] = None
        self._retriever = None

    def _default_config(self) -> ModeConfig:
        return ModeConfig(
            mode_type=ModeType.CONCLUDE,
            has_memory=True,
            system_prompt=load_prompt("conclude.md"),
            verbose=False,
        )

    async def _initialize(self) -> None:
        if self._index is None:
            raise ValueError("ConcludeMode requires a pgvector index")
        await self._refresh_engine()

    async def _refresh_engine(self) -> None:
        _, _, allowed_ids = build_document_filters(self.allowed_doc_ids, key="ref_doc_id")

        if self._es_index is not None:
            pg_filters, es_filters, _ = build_document_filters(self.allowed_doc_ids, key="ref_doc_id")
            self._retriever = build_hybrid_retriever(
                pgvector_index=self._index,
                es_index=self._es_index,
                pgvector_top_k=self._similarity_top_k,
                es_top_k=self._similarity_top_k,
                final_top_k=self._similarity_top_k,
                pg_filters=pg_filters,
                es_filters=es_filters,
                allowed_doc_ids=allowed_ids,
            )
        else:
            # Fallback for environments without ES index.
            base_retriever = self._index.as_retriever(
                similarity_top_k=self._similarity_top_k,
                filters=None,
            )
            self._retriever = ScopedRetriever(
                base_retriever=base_retriever,
                allowed_doc_ids=allowed_ids,
                top_k=self._similarity_top_k,
            )

        self._chat_engine = CondensePlusContextChatEngine.from_defaults(
            retriever=self._retriever,
            llm=self._llm,
            memory=self._memory,
            system_prompt=self._config.system_prompt or load_prompt("conclude.md"),
            context_prompt=DEFAULT_CONCLUDE_CONTEXT_PROMPT,
            skip_condense=get_conclude_skip_condense(),
            verbose=self._config.verbose,
        )

    def _build_enhanced_query(self, message: str) -> str:
        """Compose query using selected_text when available."""
        selection = self.get_selected_text()
        if not selection:
            return message

        return (
            "请对以下选中的文本内容进行总结:\n\n"
            f"选中内容:\n---\n{selection}\n---\n\n"
            f"用户要求: {message}\n\n"
            "要求:\n1. 提取核心观点\n2. 按逻辑顺序组织总结\n3. 内容较长则分点列出关键信息\n4. 如有上下文缺失可标注假设"
        )

    async def _process(self, message: str) -> str:
        if self.scope_changed():
            await self._refresh_engine()

        query = self._build_enhanced_query(message)
        response = await self._chat_engine.achat(query)

        sources = []
        source_nodes = getattr(response, "source_nodes", None)
        if source_nodes:
            for n in source_nodes:
                doc_id = extract_document_id(n)
                sources.append(
                    {
                        "document_id": doc_id,
                        "chunk_id": getattr(n.node, "node_id", ""),
                        "text": n.node.get_content(),
                        "score": getattr(n, "score", 0.0),
                    }
                )

        selection = self.get_selected_text()
        doc_id = self.get_context_document_id()
        if selection and doc_id:
            sources.insert(
                0,
                {
                    "document_id": doc_id,
                    "chunk_id": getattr(self._context, "chunk_id", None) or "user_selection",
                    "text": selection,
                    "score": 1.0,
                },
            )

        self._last_sources = sources
        return response.response

    async def _stream(self, message: str):
        if self.scope_changed():
            await self._refresh_engine()
        query = self._build_enhanced_query(message)

        stream_response = await self._chat_engine.astream_chat(query)
        async for token in stream_response.async_response_gen():
            if token:
                yield token

        sources = []
        for sn in getattr(stream_response, "source_nodes", []) or []:
            doc_id = extract_document_id(sn)
            sources.append(
                {
                    "document_id": doc_id,
                    "chunk_id": getattr(sn.node, "node_id", ""),
                    "text": sn.node.get_content(),
                    "score": getattr(sn, "score", 0.0),
                }
            )

        selection = self.get_selected_text()
        doc_id = self.get_context_document_id()
        if selection and doc_id:
            sources.insert(
                0,
                {
                    "document_id": doc_id,
                    "chunk_id": getattr(self._context, "chunk_id", None) or "user_selection",
                    "text": selection,
                    "score": 1.0,
                },
            )
        self._last_sources = sources

    @property
    def chat_engine(self) -> Optional[BaseChatEngine]:
        return self._chat_engine

    async def reset(self) -> None:
        if self._memory is not None:
            self._memory.reset()
        if self._chat_engine is not None:
            self._chat_engine.reset()


def build_conclude_mode(
    llm: LLM,
    index: VectorStoreIndex,
    es_index: Optional[VectorStoreIndex] = None,
    similarity_top_k: int = 8,
) -> ConcludeMode:
    """Build a ConcludeMode instance."""
    return ConcludeMode(
        llm=llm,
        index=index,
        es_index=es_index,
        similarity_top_k=similarity_top_k,
    )

