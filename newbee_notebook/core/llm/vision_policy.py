"""Vision model selection for user-uploaded chat images."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VisionModelDecision:
    provider: str
    model: str
    used_fallback: bool = False


class VisionPolicy:
    """Resolve the model used when a chat turn includes uploaded images."""

    DEFAULT_VISION_MODELS = {
        "qwen": "qwen3.5-plus",
        "zhipu": "glm-5v-turbo",
    }
    VISION_MODELS = {
        "qwen": {
            "qwen3.5-plus",
            "qwen-vl-plus",
            "qwen-vl-max",
            "qwen2.5-vl-72b-instruct",
        },
        "zhipu": {
            "glm-5v-turbo",
            "glm-5.1v-turbo",
            "glm-4.6v",
            "glm-4.6v-flash",
            "glm-4.6v-flashx",
        },
    }

    def resolve(self, runtime_config: Any) -> VisionModelDecision:
        provider = str(getattr(runtime_config, "provider", "") or "").strip().lower()
        model = str(getattr(runtime_config, "model", "") or "").strip()
        normalized_model = model.lower()
        provider_models = self.VISION_MODELS.get(provider, set())

        if provider_models and normalized_model in provider_models:
            return VisionModelDecision(
                provider=provider,
                model=model,
                used_fallback=False,
            )

        fallback = self.DEFAULT_VISION_MODELS.get(provider)
        if not fallback:
            raise ValueError(
                f"Provider '{provider or 'unknown'}' does not have a configured vision fallback model."
            )
        return VisionModelDecision(
            provider=provider,
            model=fallback,
            used_fallback=True,
        )
