import subprocess
import time

import pytest
import requests

from newbee_notebook.infrastructure.document_processing.converters.mineru_cloud_converter import (
    MinerUCloudConverter,
    MinerUCloudTransientError,
)


class _RaiseInContext:
    def __init__(self, exc: Exception):
        self._exc = exc

    def __enter__(self):
        raise self._exc

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


def _make_converter(**kwargs) -> MinerUCloudConverter:
    return MinerUCloudConverter(
        api_key="dummy-key",
        timeout_seconds=60,
        poll_interval=5,
        max_wait_seconds=1800,
        **kwargs,
    )


def test_download_zip_falls_back_to_curl_on_ssl_error(monkeypatch):
    converter = _make_converter(enable_curl_fallback=True)
    calls = {"req": 0, "curl": 0}

    def _fail_get(*args, **kwargs):  # noqa: ARG001
        calls["req"] += 1
        return _RaiseInContext(requests.exceptions.SSLError("ssl eof"))

    def _curl_ok(url: str, max_retries: int = 3):  # noqa: ARG001
        calls["curl"] += 1
        return b"zip-bytes"

    monkeypatch.setattr(requests, "get", _fail_get)
    monkeypatch.setattr(converter, "_resolve_host_ips", lambda _host: [])
    monkeypatch.setattr(converter, "_download_zip_with_curl", _curl_ok)
    monkeypatch.setattr(time, "sleep", lambda _secs: None)

    result = converter._download_zip("https://cdn-mineru.openxlab.org.cn/pdf/result.zip", max_retries=3)

    assert result == b"zip-bytes"
    assert calls["req"] == 3
    assert calls["curl"] == 1


def test_download_zip_reports_both_requests_and_curl_errors(monkeypatch):
    converter = _make_converter(enable_curl_fallback=True)

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _RaiseInContext(requests.exceptions.ConnectionError("conn reset")),  # noqa: ARG005
    )
    monkeypatch.setattr(converter, "_resolve_host_ips", lambda _host: ["1.2.3.4"])
    monkeypatch.setattr(
        converter,
        "_download_zip_with_curl",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("curl failed")),
    )
    monkeypatch.setattr(time, "sleep", lambda _secs: None)

    with pytest.raises(MinerUCloudTransientError) as exc_info:
        converter._download_zip("https://cdn-mineru.openxlab.org.cn/pdf/result.zip", max_retries=3)

    text = str(exc_info.value)
    assert "both requests and curl fallback" in text
    assert "conn reset" in text
    assert "curl failed" in text


def test_download_zip_without_curl_fallback_keeps_original_error(monkeypatch):
    converter = _make_converter(enable_curl_fallback=False)

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _RaiseInContext(requests.exceptions.SSLError("ssl eof")),  # noqa: ARG005
    )
    monkeypatch.setattr(converter, "_resolve_host_ips", lambda _host: [])
    monkeypatch.setattr(time, "sleep", lambda _secs: None)

    with pytest.raises(MinerUCloudTransientError) as exc_info:
        converter._download_zip("https://cdn-mineru.openxlab.org.cn/pdf/result.zip", max_retries=3)

    assert "failed after 3 retries" in str(exc_info.value)


def test_download_zip_with_curl_command_success(monkeypatch):
    converter = _make_converter(enable_curl_fallback=True, curl_binary="curl")

    class _Result:
        returncode = 0
        stdout = b"zip-binary"
        stderr = b""

    monkeypatch.setattr(converter, "_resolve_curl_binary", lambda: "curl")

    def _fake_run(cmd, capture_output, check, env):  # noqa: ARG001
        assert cmd[0] == "curl"
        assert "--retry-all-errors" in cmd
        assert "--output" in cmd
        return _Result()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    out = converter._download_zip_with_curl("https://cdn-mineru.openxlab.org.cn/pdf/result.zip", max_retries=2)
    assert out == b"zip-binary"
