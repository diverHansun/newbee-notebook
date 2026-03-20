from __future__ import annotations

import pytest

from newbee_notebook.application.services.diagram_service import (
    DiagramTypeNotFoundError,
    DiagramValidationError,
)
from newbee_notebook.skills.diagram.registry import (
    get_descriptor,
    infer_diagram_type_from_prompt,
    validate_reactflow_schema,
)


def test_valid_reactflow_json_passes():
    validate_reactflow_schema(
        '{"nodes":[{"id":"root","label":"Topic"},{"id":"n1","label":"Subtopic"}],'
        '"edges":[{"source":"root","target":"n1"}]}'
    )


def test_invalid_json_raises():
    with pytest.raises(DiagramValidationError, match="Invalid JSON"):
        validate_reactflow_schema("not json")


def test_missing_nodes_raises():
    with pytest.raises(DiagramValidationError, match="schema validation failed"):
        validate_reactflow_schema('{"edges":[]}')


def test_node_with_position_raises():
    content = '{"nodes":[{"id":"root","label":"x","position":{"x":0,"y":0}}],"edges":[]}'
    with pytest.raises(DiagramValidationError, match="position"):
        validate_reactflow_schema(content)


def test_get_descriptor_known_type():
    descriptor = get_descriptor("mindmap")
    assert descriptor.output_format == "reactflow_json"


def test_get_descriptor_flowchart_and_sequence():
    flowchart = get_descriptor("flowchart")
    sequence = get_descriptor("sequence")

    assert flowchart.output_format == "reactflow_json"
    assert sequence.output_format == "reactflow_json"


def test_get_descriptor_unknown_type():
    with pytest.raises(DiagramTypeNotFoundError):
        get_descriptor("unknown_type")


def test_infer_diagram_type_from_prompt():
    assert infer_diagram_type_from_prompt("Please generate a mind map for chapter 3") == "mindmap"
    assert infer_diagram_type_from_prompt("Please generate a flow chart for onboarding") == "flowchart"
    assert infer_diagram_type_from_prompt("Please generate a sequence diagram for login") == "sequence"
    assert infer_diagram_type_from_prompt("Please visualize this chapter") is None
