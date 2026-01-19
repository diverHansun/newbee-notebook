"""Prompt loading utilities."""

from pathlib import Path


def load_prompt(file_name: str) -> str:
    """Load a prompt markdown file from src/prompts."""
    path = Path(__file__).resolve().parent / file_name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


