from types import SimpleNamespace

from newbee_notebook.core.llm.vision_policy import VisionPolicy


def test_vision_policy_keeps_vision_capable_chat_model():
    policy = VisionPolicy()

    decision = policy.resolve(SimpleNamespace(provider="qwen", model="qwen3.5-plus"))

    assert decision.model == "qwen3.5-plus"
    assert decision.used_fallback is False


def test_vision_policy_falls_back_to_provider_default_without_mutating_runtime_config():
    policy = VisionPolicy()
    runtime_config = SimpleNamespace(provider="zhipu", model="glm-5")

    decision = policy.resolve(runtime_config)

    assert decision.model == "glm-5v-turbo"
    assert decision.used_fallback is True
    assert runtime_config.model == "glm-5"
