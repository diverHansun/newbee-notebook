from __future__ import annotations

import pytest

from newbee_notebook.application.services.diagram_service import (
    DiagramTypeNotFoundError,
    DiagramValidationError,
)
from newbee_notebook.skills.diagram.registry import (
    DIAGRAM_TYPE_REGISTRY,
    build_diagram_system_prompt,
    get_descriptor,
    infer_diagram_type_from_prompt,
    validate_mermaid_syntax,
    validate_reactflow_schema,
)


def test_valid_reactflow_json_passes():
    validate_reactflow_schema(
        '{"nodes":[{"id":"root","label":"Topic"},{"id":"n1","label":"Subtopic"}],'
        '"edges":[{"source":"root","target":"n1"}]}'
    )


def test_invalid_json_raises():
    with pytest.raises(DiagramValidationError, match="structure"):
        validate_reactflow_schema("not json")


def test_mindmap_rejects_markdown_fence():
    with pytest.raises(DiagramValidationError, match="structure"):
        validate_reactflow_schema('```json\n{"nodes":[],"edges":[]}\n```')


def test_mindmap_rejects_extra_top_level_key():
    with pytest.raises(DiagramValidationError, match="schema"):
        validate_reactflow_schema(
            '{"nodes":[{"id":"root","label":"Root"}],"edges":[],"meta":{"x":1}}'
        )


def test_mindmap_rejects_position_field():
    content = '{"nodes":[{"id":"root","label":"x","position":{"x":0,"y":0}}],"edges":[]}'
    with pytest.raises(DiagramValidationError, match="position"):
        validate_reactflow_schema(content)


def test_mindmap_rejects_duplicate_ids():
    with pytest.raises(DiagramValidationError, match="schema"):
        validate_reactflow_schema(
            '{"nodes":[{"id":"root","label":"A"},{"id":"root","label":"B"}],"edges":[]}'
        )


def test_mindmap_rejects_edge_to_unknown_node():
    with pytest.raises(DiagramValidationError, match="reference"):
        validate_reactflow_schema(
            '{"nodes":[{"id":"root","label":"A"}],"edges":[{"source":"root","target":"n2"}]}'
        )


def test_mindmap_rejects_self_loop():
    with pytest.raises(DiagramValidationError, match="schema"):
        validate_reactflow_schema(
            '{"nodes":[{"id":"root","label":"A"}],"edges":[{"source":"root","target":"root"}]}'
        )


def test_valid_mermaid_syntax_passes():
    validate_mermaid_syntax('flowchart TD\nA["Start"] --> B["Finish"]')


def test_invalid_mermaid_syntax_raises():
    with pytest.raises(DiagramValidationError, match="syntax"):
        validate_mermaid_syntax("plain text without a diagram declaration")


def test_mermaid_rejects_markdown_fence():
    with pytest.raises(DiagramValidationError, match="structure"):
        validate_mermaid_syntax("```mermaid\nflowchart TD\nA --> B\n```")


def test_flowchart_rejects_invalid_direction():
    with pytest.raises(DiagramValidationError, match="syntax"):
        validate_mermaid_syntax("flowchart TOP\nA --> B")


def test_flowchart_rejects_reserved_end_id():
    with pytest.raises(DiagramValidationError, match="reserved"):
        validate_mermaid_syntax("flowchart TD\nend --> B")


def test_flowchart_rejects_id_starting_with_o_or_x():
    with pytest.raises(DiagramValidationError, match="reserved"):
        validate_mermaid_syntax("flowchart TD\norigin --> B")


def test_flowchart_rejects_unquoted_label_with_parentheses():
    with pytest.raises(DiagramValidationError, match="escape"):
        validate_mermaid_syntax("flowchart TD\nA[执行(步骤1)] --> B[结束]")


def test_flowchart_allows_subgraph_end_keyword():
    validate_mermaid_syntax(
        "flowchart TD\nsubgraph Cluster\nA[Start] --> B[Finish]\nend\nB --> C[Done]"
    )


def test_sequence_rejects_extra_tokens_on_header():
    with pytest.raises(DiagramValidationError, match="syntax"):
        validate_mermaid_syntax("sequenceDiagram LR\nA->>B: hello")


def test_sequence_rejects_reserved_end_participant():
    with pytest.raises(DiagramValidationError, match="reserved"):
        validate_mermaid_syntax("sequenceDiagram\nparticipant end\nA->>end: hi")


def test_sequence_rejects_unescaped_semicolon():
    with pytest.raises(DiagramValidationError, match="escape"):
        validate_mermaid_syntax("sequenceDiagram\nA->>B: step1; step2")


def test_build_diagram_system_prompt_contains_each_type():
    prompt = build_diagram_system_prompt()
    assert "mindmap" in prompt
    assert "flowchart" in prompt
    assert "sequence" in prompt
    assert "mindmap JSON schema" in prompt
    assert "<tool_call>" in prompt


def test_descriptor_positive_examples_pass_their_validator():
    for descriptor in DIAGRAM_TYPE_REGISTRY.values():
        descriptor.validator(descriptor.positive_example)


def test_get_descriptor_known_type():
    descriptor = get_descriptor("mindmap")
    assert descriptor.output_format == "reactflow_json"


def test_get_descriptor_flowchart_and_sequence():
    flowchart = get_descriptor("flowchart")
    sequence = get_descriptor("sequence")

    assert flowchart.output_format == "mermaid"
    assert flowchart.file_extension == ".mmd"
    assert sequence.output_format == "mermaid"
    assert sequence.file_extension == ".mmd"


def test_get_descriptor_unknown_type():
    with pytest.raises(DiagramTypeNotFoundError):
        get_descriptor("unknown_type")


def test_infer_diagram_type_from_prompt():
    assert infer_diagram_type_from_prompt("Please generate a mind map for chapter 3") == "mindmap"
    assert infer_diagram_type_from_prompt("Please generate a flow chart for onboarding") == "flowchart"
    assert infer_diagram_type_from_prompt("Please generate a sequence diagram for login") == "sequence"
    assert infer_diagram_type_from_prompt("Please visualize this chapter") is None
