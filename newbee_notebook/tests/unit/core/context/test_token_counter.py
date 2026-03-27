import tiktoken

from newbee_notebook.core.context.budget import ContextBudget
from newbee_notebook.core.context.token_counter import TokenCounter


def test_token_counter_uses_tiktoken_for_mixed_text():
    counter = TokenCounter()
    encoding = tiktoken.get_encoding("cl100k_base")
    text = "中英 mixed text 压缩"

    assert counter.count(text) == len(encoding.encode(text))


def test_token_counter_treats_empty_like_zero_tokens():
    counter = TokenCounter()

    assert counter.count("") == 0
    assert counter.count("   ") == 0
    assert counter.count(None) == 0


def test_token_counter_adds_message_overhead():
    counter = TokenCounter()

    assert counter.count_messages([{"role": "user", "content": "hello"}]) > counter.count("hello")


def test_context_budget_exposes_summary_and_compaction_threshold():
    budget = ContextBudget(
        total=200_000,
        system_prompt=2_000,
        history=170_000,
        summary=6_000,
        current_message=4_000,
        tool_results=8_000,
        output_reserved=8_000,
        main_injection=2_000,
    )

    assert budget.summary == 6_000
    assert budget.compaction_threshold == 190_000
