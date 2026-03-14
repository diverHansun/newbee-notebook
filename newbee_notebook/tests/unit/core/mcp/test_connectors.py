from __future__ import annotations

from types import SimpleNamespace

import pytest

from newbee_notebook.core.mcp.connectors import connect_mcp_server
from newbee_notebook.core.mcp.types import MCPServerConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _AsyncContext:
    def __init__(self, value, on_exit=None):
        self._value = value
        self._on_exit = on_exit

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, exc_type, exc, tb):
        if self._on_exit is not None:
            self._on_exit()


@pytest.mark.anyio
async def test_connect_stdio_server_initializes_client_and_closes_resources(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, object] = {}

    def _fake_stdio_client(server):
        calls["server"] = server
        return _AsyncContext(("read-stream", "write-stream"), on_exit=lambda: calls.setdefault("transport_closed", True))

    class _FakeSession:
        def __init__(self, read_stream, write_stream):
            calls["session_args"] = (read_stream, write_stream)

        async def __aenter__(self):
            calls["session_entered"] = True
            return self

        async def __aexit__(self, exc_type, exc, tb):
            calls["session_closed"] = True

        async def initialize(self):
            calls["initialized"] = True

        async def list_tools(self):
            return SimpleNamespace(
                tools=[
                    SimpleNamespace(
                        name="read_file",
                        description="Read file",
                        inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
                    )
                ]
            )

        async def call_tool(self, name, arguments):
            return {"content": [{"type": "text", "text": f"{name}:{arguments['path']}"}]}

    monkeypatch.setattr("newbee_notebook.core.mcp.connectors.stdio_client", _fake_stdio_client)
    monkeypatch.setattr("newbee_notebook.core.mcp.connectors.ClientSession", _FakeSession)

    client = await connect_mcp_server(
        MCPServerConfig(
            name="filesystem",
            transport="stdio",
            command="python",
            args=["-m", "filesystem_server"],
            env={"TOKEN": "abc"},
        )
    )

    tools = await client.list_tools()
    result = await client.call_tool("read_file", {"path": "notes.txt"})
    await client.close()

    assert calls["initialized"] is True
    assert calls["session_args"] == ("read-stream", "write-stream")
    assert [tool.name for tool in tools] == ["read_file"]
    assert result["content"][0]["text"] == "read_file:notes.txt"
    assert calls["session_closed"] is True
    assert calls["transport_closed"] is True


@pytest.mark.anyio
async def test_connect_streamable_http_server_uses_headers_and_url(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, object] = {}

    def _fake_streamable_http_client(url, headers=None, **kwargs):
        calls["url"] = url
        calls["headers"] = headers
        calls["kwargs"] = kwargs
        return _AsyncContext(("read-stream", "write-stream", lambda: "session-1"), on_exit=lambda: calls.setdefault("transport_closed", True))

    class _FakeSession:
        def __init__(self, read_stream, write_stream):
            calls["session_args"] = (read_stream, write_stream)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            calls["session_closed"] = True

        async def initialize(self):
            calls["initialized"] = True

        async def list_tools(self):
            return SimpleNamespace(tools=[])

        async def call_tool(self, name, arguments):
            return {"content": [{"type": "text", "text": name}]}

    monkeypatch.setattr("newbee_notebook.core.mcp.connectors.streamablehttp_client", _fake_streamable_http_client)
    monkeypatch.setattr("newbee_notebook.core.mcp.connectors.ClientSession", _FakeSession)

    client = await connect_mcp_server(
        MCPServerConfig(
            name="weather",
            transport="streamable-http",
            url="https://example.com/mcp",
            headers={"Authorization": "Bearer test-token"},
        )
    )
    await client.close()

    assert calls["url"] == "https://example.com/mcp"
    assert calls["headers"] == {"Authorization": "Bearer test-token"}
    assert calls["initialized"] is True
    assert calls["session_args"] == ("read-stream", "write-stream")
    assert calls["session_closed"] is True
    assert calls["transport_closed"] is True
