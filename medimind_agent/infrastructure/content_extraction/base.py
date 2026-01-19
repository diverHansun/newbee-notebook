"""
Content extraction interface and simple factory.
"""

import os
from typing import Optional


class ExtractionResult:
    def __init__(self, text: str, page_count: int = 1):
        self.text = text
        self.page_count = page_count


class BaseExtractor:
    def can_handle(self, ext: str) -> bool:
        raise NotImplementedError

    def extract(self, path: str) -> ExtractionResult:
        raise NotImplementedError


class TxtExtractor(BaseExtractor):
    def can_handle(self, ext: str) -> bool:
        return ext in {".txt", ".md", ".markdown"}

    def extract(self, path: str) -> ExtractionResult:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return ExtractionResult(text=text, page_count=1)


class PdfExtractor(BaseExtractor):
    def can_handle(self, ext: str) -> bool:
        return ext == ".pdf"

    def extract(self, path: str) -> ExtractionResult:
        try:
            import PyPDF2
        except ImportError:
            raise RuntimeError("PyPDF2 not installed; cannot process PDF")
        reader = PyPDF2.PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return ExtractionResult(text="\n".join(pages), page_count=len(pages))


class DocxExtractor(BaseExtractor):
    def can_handle(self, ext: str) -> bool:
        return ext in {".docx"}

    def extract(self, path: str) -> ExtractionResult:
        try:
            import docx2txt
        except ImportError:
            raise RuntimeError("docx2txt not installed; cannot process docx")
        text = docx2txt.process(path) or ""
        return ExtractionResult(text=text, page_count=1)


class ExcelExtractor(BaseExtractor):
    def can_handle(self, ext: str) -> bool:
        return ext in {".xlsx", ".xls"}

    def extract(self, path: str) -> ExtractionResult:
        import pandas as pd

        frames = pd.read_excel(path, sheet_name=None)
        texts = []
        for name, df in frames.items():
            texts.append(f"[Sheet: {name}]\n{df.to_csv(index=False)}")
        return ExtractionResult(text="\n".join(texts), page_count=1)


class CsvExtractor(BaseExtractor):
    def can_handle(self, ext: str) -> bool:
        return ext == ".csv"

    def extract(self, path: str) -> ExtractionResult:
        import pandas as pd

        df = pd.read_csv(path)
        return ExtractionResult(text=df.to_csv(index=False), page_count=1)


EXTRACTORS = [
    PdfExtractor(),
    DocxExtractor(),
    ExcelExtractor(),
    CsvExtractor(),
    TxtExtractor(),
]


def get_extractor(path: str) -> BaseExtractor:
    ext = os.path.splitext(path)[1].lower()
    for extractor in EXTRACTORS:
        if extractor.can_handle(ext):
            return extractor
    raise RuntimeError(f"Unsupported file type: {ext}")
