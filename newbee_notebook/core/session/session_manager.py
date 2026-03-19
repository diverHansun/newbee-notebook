"""Request-scoped session orchestration for the batch-2 runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, AsyncGenerator, Callable

from newbee_notebook.core.context import (
    Compressor,
    ContextBudget,
    ContextBuilder,
    SessionMemory,
    StoredMessage,
    TokenCounter,
)
from newbee_notebook.core.engine.confirmation import ConfirmationGateway
from newbee_notebook.core.engine.agent_loop import AgentLoop
from newbee_notebook.core.engine.mode_config import ModeConfigFactory
from newbee_notebook.core.engine.stream_events import (
    ContentEvent,
    ErrorEvent,
    SourceEvent,
    WarningEvent,
)
from newbee_notebook.core.prompts import load_prompt
from newbee_notebook.core.session.lock_manager import SessionLockManager
from newbee_notebook.core.tools.contracts import SourceItem
from newbee_notebook.domain.entities.session import Session
from newbee_notebook.domain.repositories.message_repository import MessageRepository
from newbee_notebook.domain.repositories.session_repository import SessionRepository
from newbee_notebook.domain.value_objects.mode_type import MessageRole, ModeType, normalize_runtime_mode


@lru_cache(maxsize=8)
def _load_mode_prompt(mode: ModeType) -> str:
    if mode in (ModeType.AGENT, ModeType.CHAT):
        return load_prompt("chat.md")
    if mode is ModeType.ASK:
        return load_prompt("ask.md")
    if mode is ModeType.EXPLAIN:
        return load_prompt("explain.md")
    if mode is ModeType.CONCLUDE:
        return load_prompt("conclude.md")
    return f"You are running in {mode.value} mode."


@dataclass(frozen=True)
class SessionRunResult:
    content: str
    sources: list[SourceItem] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


class SessionManager:
    MAIN_TRACK_MODES = (ModeType.AGENT, ModeType.CHAT, ModeType.ASK)
    SIDE_TRACK_MODES = (ModeType.EXPLAIN, ModeType.CONCLUDE)

    def __init__(
        self,
        *,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        llm_client: Any,
        tool_registry: Any,
        lock_manager: SessionLockManager | None = None,
        agent_loop_cls: type[AgentLoop] = AgentLoop,
        system_prompt_provider: Callable[[ModeType], str] | None = None,
        confirmation_gateway: ConfirmationGateway | None = None,
    ):
        self._session_repo = session_repo
        self._message_repo = message_repo
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._lock_manager = lock_manager or SessionLockManager()
        self._agent_loop_cls = agent_loop_cls
        self._system_prompt_provider = system_prompt_provider or self._default_system_prompt
        self._confirmation_gateway = confirmation_gateway
        self._current_session: Session | None = None
        self._current_mode: ModeType = ModeType.AGENT
        self._memory = SessionMemory()
        self._last_sources: list[SourceItem] = []

    @property
    def session_id(self) -> str | None:
        return self._current_session.session_id if self._current_session else None

    @property
    def current_mode(self) -> ModeType:
        return self._current_mode

    def switch_mode(self, mode_type: ModeType) -> None:
        self._current_mode = normalize_runtime_mode(mode_type)

    async def start_session(
        self,
        *,
        session_id: str | None = None,
        notebook_id: str | None = None,
    ) -> Session:
        if session_id:
            session = await self._session_repo.get(session_id)
            if not session:
                raise ValueError(f"Session not found: {session_id}")
        else:
            if not notebook_id:
                raise ValueError("notebook_id is required to create a session")
            session = await self._session_repo.create(Session(notebook_id=notebook_id))
        self._current_session = session
        await self._reload_memory()
        return session

    async def _reload_memory(self) -> None:
        if not self._current_session:
            return

        main_messages = await self._message_repo.list_by_session(
            self._current_session.session_id,
            limit=50,
            modes=list(self.MAIN_TRACK_MODES),
        )
        side_messages = await self._message_repo.list_by_session(
            self._current_session.session_id,
            limit=12,
            modes=list(self.SIDE_TRACK_MODES),
        )

        self._memory.load_from_messages(
            main_messages=[self._to_stored_message(item) for item in main_messages],
            side_messages=[self._to_stored_message(item) for item in side_messages],
        )

    @staticmethod
    def _to_stored_message(message) -> StoredMessage:
        return StoredMessage(
            role=_normalize_message_role(message.role),
            content=message.content,
            mode=_normalize_message_mode(message.mode),
        )

    @staticmethod
    def _default_system_prompt(mode: ModeType) -> str:
        return _load_mode_prompt(mode)

    def _build_chat_history(
        self,
        mode: ModeType,
        system_prompt_addition: str = "",
    ) -> list[dict[str, str]]:
        builder = ContextBuilder(
            memory=self._memory,
            token_counter=TokenCounter(),
            compressor=Compressor(token_counter=TokenCounter()),
        )
        track = "side" if mode in self.SIDE_TRACK_MODES else "main"
        system_prompt = self._system_prompt_provider(mode)
        if system_prompt_addition.strip():
            system_prompt = f"{system_prompt}\n\n{system_prompt_addition.strip()}"
        return builder.build(
            track=track,
            system_prompt=system_prompt,
            current_message="",
            budget=ContextBudget(
                total=4096,
                system_prompt=512,
                history=2048,
                current_message=512,
                tool_results=512,
                output_reserved=512,
                main_injection=512,
            ),
            inject_main=track == "side",
        )

    @staticmethod
    def _build_runtime_message(
        *,
        mode: ModeType,
        message: str,
        allowed_document_ids: list[str] | None,
        context: dict | None,
    ) -> str:
        normalized_message = str(message or "").strip()
        if mode not in SessionManager.SIDE_TRACK_MODES:
            if not allowed_document_ids:
                return normalized_message

            document_count = len(allowed_document_ids)
            return (
                "Notebook context:\n"
                f"- The current notebook already contains {document_count} completed document"
                f"{'' if document_count == 1 else 's'} available through the knowledge_base tool.\n"
                "- For notebook-specific questions, use the knowledge_base tool before answering.\n\n"
                "User request:\n"
                f"{normalized_message}"
            )

        selected_text = str((context or {}).get("selected_text") or "").strip()
        if not selected_text:
            return normalized_message

        default_instruction = (
            "Explain the selected text using grounded notebook evidence."
            if mode is ModeType.EXPLAIN
            else "Conclude the selected text using grounded notebook evidence."
        )
        instruction = normalized_message or default_instruction
        return (
            "Selected text:\n"
            f"{selected_text}\n\n"
            "User request:\n"
            f"{instruction}"
        )

    @staticmethod
    def _build_tool_argument_defaults(
        *,
        mode: ModeType,
        mode_config: Any,
        allowed_document_ids: list[str] | None,
        context: dict | None,
    ) -> dict[str, dict[str, Any]]:
        default_tool_name = mode_config.tool_policy.default_tool_name
        if not default_tool_name:
            return {}

        defaults = dict(mode_config.tool_policy.default_tool_args_template)
        if allowed_document_ids is not None:
            defaults["allowed_document_ids"] = list(allowed_document_ids)
        if mode in SessionManager.SIDE_TRACK_MODES:
            document_id = str((context or {}).get("document_id") or "").strip()
            if document_id:
                defaults["filter_document_id"] = document_id

        return {default_tool_name: defaults}

    async def _build_loop(
        self,
        *,
        mode: ModeType,
        allowed_document_ids: list[str] | None,
        context: dict | None,
        external_tools: list[Any] | None = None,
        confirmation_required: frozenset[str] | None = None,
        confirmation_gateway: ConfirmationGateway | None = None,
    ):
        effective_confirmation_gateway = confirmation_gateway or self._confirmation_gateway
        tools = await self._tool_registry.get_tools(mode.value, external_tools=external_tools)
        mode_config = ModeConfigFactory.build(mode, tools)
        tool_argument_defaults = self._build_tool_argument_defaults(
            mode=mode,
            mode_config=mode_config,
            allowed_document_ids=allowed_document_ids,
            context=context,
        )
        return self._agent_loop_cls(
            llm_client=self._llm_client,
            tools=tools,
            mode_config=mode_config,
            tool_argument_defaults=tool_argument_defaults,
            confirmation_required=confirmation_required,
            confirmation_gateway=effective_confirmation_gateway,
        )

    async def chat_stream(
        self,
        *,
        message: str,
        mode_type: ModeType | None = None,
        allowed_document_ids: list[str] | None = None,
        context: dict | None = None,
        include_ec_context: bool = False,
        external_tools: list[Any] | None = None,
        system_prompt_addition: str = "",
        confirmation_required: frozenset[str] | None = None,
        confirmation_gateway: ConfirmationGateway | None = None,
    ) -> AsyncGenerator[Any, None]:
        del include_ec_context
        if not self._current_session:
            raise ValueError("Session not started")

        mode = normalize_runtime_mode(mode_type or self._current_mode)
        self._current_mode = mode
        chat_history = self._build_chat_history(mode, system_prompt_addition=system_prompt_addition)
        loop = await self._build_loop(
            mode=mode,
            allowed_document_ids=allowed_document_ids,
            context=context,
            external_tools=external_tools,
            confirmation_required=confirmation_required,
            confirmation_gateway=confirmation_gateway,
        )
        runtime_message = self._build_runtime_message(
            mode=mode,
            message=message,
            allowed_document_ids=allowed_document_ids,
            context=context,
        )

        async with self._lock_manager.acquire(self._current_session.session_id):
            async for event in loop.stream(message=runtime_message, chat_history=chat_history):
                if isinstance(event, SourceEvent):
                    self._last_sources = list(event.sources)
                yield event

    async def chat(
        self,
        *,
        message: str,
        mode_type: ModeType | None = None,
        allowed_document_ids: list[str] | None = None,
        context: dict | None = None,
        include_ec_context: bool = False,
        external_tools: list[Any] | None = None,
        system_prompt_addition: str = "",
        confirmation_required: frozenset[str] | None = None,
        confirmation_gateway: ConfirmationGateway | None = None,
    ) -> SessionRunResult:
        content_parts: list[str] = []
        sources: list[SourceItem] = []
        warnings: list[dict[str, Any]] = []

        async for event in self.chat_stream(
            message=message,
            mode_type=mode_type,
            allowed_document_ids=allowed_document_ids,
            context=context,
            include_ec_context=include_ec_context,
            external_tools=external_tools,
            system_prompt_addition=system_prompt_addition,
            confirmation_required=confirmation_required,
            confirmation_gateway=confirmation_gateway,
        ):
            if isinstance(event, ContentEvent):
                content_parts.append(event.delta)
            elif isinstance(event, SourceEvent):
                sources = list(event.sources)
            elif isinstance(event, WarningEvent):
                warnings.append({"code": event.code, "message": event.message})
            elif isinstance(event, ErrorEvent):
                raise RuntimeError(event.message)

        return SessionRunResult(
            content="".join(content_parts),
            sources=sources,
            warnings=warnings,
        )

    def get_last_sources(self) -> list[SourceItem]:
        return list(self._last_sources)

def _normalize_message_role(role: MessageRole | str) -> str:
    return role.value if hasattr(role, "value") else str(role)


def _normalize_message_mode(mode: ModeType | str) -> str:
    value = mode.value if hasattr(mode, "value") else str(mode)
    normalized = value.strip().lower()
    known = {item.value for item in ModeType}
    if normalized in known:
        return normalize_runtime_mode(normalized).value
    return normalized
