"""Runtime skill providers."""

from newbee_notebook.skills.diagram import DiagramSkillProvider
from newbee_notebook.skills.note import NoteSkillProvider

__all__ = [
    "NoteSkillProvider",
    "DiagramSkillProvider",
]
