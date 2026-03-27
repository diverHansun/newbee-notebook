import tiktoken

from newbee_notebook.core.context.compressor import Compressor
from newbee_notebook.core.context.token_counter import TokenCounter


def test_compressor_truncate_respects_token_budget():
    encoding = tiktoken.get_encoding("cl100k_base")
    text = "Compression should keep mixed 中英 text safely within the token budget."
    compressor = Compressor(token_counter=TokenCounter())

    truncated = compressor.truncate(text, max_tokens=8)

    assert len(encoding.encode(truncated)) <= 8
    assert truncated != text


def test_compressor_keeps_text_when_within_budget():
    compressor = Compressor(token_counter=TokenCounter())
    text = "short text"

    assert compressor.truncate(text, max_tokens=50) == text
