"""Prompt loading utilities."""

from pathlib import Path


def load_prompt(file_name: str, lang: str = "en") -> str:
    """Load a prompt markdown file with language support.

    Args:
        file_name: Base file name without language suffix (e.g., "chat")
        lang: Language code, "en" or "zh". Defaults to "en".

    Returns:
        Prompt content as string.

    Raises:
        FileNotFoundError: If the language-specific prompt file is not found.
    """
    lang = "en" if lang not in ("en", "zh") else lang
    path = Path(__file__).resolve().parent / f"{file_name}_{lang}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()
