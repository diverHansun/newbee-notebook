import asyncio

import magika
import pytest

from newbee_notebook.infrastructure.document_processing.converters.markitdown_converter import MarkItDownConverter


@pytest.mark.parametrize("suffix,content,expected", [
    (".txt", "Mac API document", "Mac API document"),
    (".html", "<h1>Mac document</h1><p>API only</p>", "# Mac document"),
    (".csv", "name,value\nmac,42\n", "42"),
])
def test_api_only_document_conversion_never_initializes_magika(monkeypatch, tmp_path, suffix, content, expected):
    monkeypatch.setenv("NEWBEE_API_ONLY", "true")
    def forbid_model(*args, **kwargs):
        raise AssertionError("Local file classification model initialized")
    monkeypatch.setattr(magika, "Magika", forbid_model)
    path = tmp_path / ("document" + suffix)
    path.write_text(content)
    converter = MarkItDownConverter()
    result = asyncio.run(converter.convert(str(path)))
    assert expected in result.markdown


def test_api_only_spreadsheet_conversion(monkeypatch, tmp_path):
    from openpyxl import Workbook

    monkeypatch.setenv("NEWBEE_API_ONLY", "true")
    def forbid_model(*args, **kwargs):
        raise AssertionError("Local file classification model initialized")
    monkeypatch.setattr(magika, "Magika", forbid_model)
    path = tmp_path / "table.xlsx"
    workbook = Workbook()
    workbook.active.append(["Platform", "Mode"])
    workbook.active.append(["macOS", "API"])
    workbook.save(path)
    result = asyncio.run(MarkItDownConverter().convert(str(path)))
    assert "macOS" in result.markdown
    assert "API" in result.markdown
