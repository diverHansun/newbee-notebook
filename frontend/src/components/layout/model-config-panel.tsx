"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  getAvailableModels,
  getModelsConfig,
  resetEmbeddingConfig,
  resetLLMConfig,
  updateEmbeddingConfig,
  updateLLMConfig,
  type EmbeddingConfig,
  type LLMConfig,
} from "@/lib/api/config";
import { ApiError } from "@/lib/api/client";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type LLMDraft = {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
};

type EmbeddingDraft = {
  provider: string;
  mode: string | null;
  api_model: string;
  model: string;
  dim: number;
};

function formatFloat(value: number): string {
  return value.toFixed(2);
}

function inferProviderByPreset(name: string, label: string): string {
  const normalized = `${name} ${label}`.toLowerCase();
  if (normalized.includes("zhipu") || normalized.includes("glm")) {
    return "zhipu";
  }
  return "qwen";
}

function toLLMDraft(config: LLMConfig): LLMDraft {
  return {
    provider: config.provider,
    model: config.model,
    temperature: config.temperature,
    max_tokens: config.max_tokens,
    top_p: config.top_p,
  };
}

function toEmbeddingDraft(config: EmbeddingConfig): EmbeddingDraft {
  return {
    provider: config.provider,
    mode: config.mode,
    api_model: config.model,
    model: config.model,
    dim: config.dim,
  };
}

export function ModelConfigPanel() {
  const { t } = useLang();
  const queryClient = useQueryClient();

  const [llmDraft, setLlmDraft] = useState<LLMDraft | null>(null);
  const [embeddingDraft, setEmbeddingDraft] = useState<EmbeddingDraft | null>(null);

  const modelDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const configQuery = useQuery({
    queryKey: ["models-config"],
    queryFn: getModelsConfig,
    staleTime: 30_000,
    retry: false,
  });

  const availableQuery = useQuery({
    queryKey: ["models-available"],
    queryFn: getAvailableModels,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });

  useEffect(() => {
    if (!configQuery.data) return;
    setLlmDraft(toLLMDraft(configQuery.data.llm));
    setEmbeddingDraft(toEmbeddingDraft(configQuery.data.embedding));
  }, [configQuery.data]);

  useEffect(() => {
    return () => {
      if (modelDebounceRef.current) {
        clearTimeout(modelDebounceRef.current);
      }
    };
  }, []);

  const llmMutation = useMutation({
    mutationFn: updateLLMConfig,
    onSuccess: (next) => {
      setLlmDraft(toLLMDraft(next));
      queryClient.setQueryData(["models-config"], (prev: any) => {
        if (!prev) return prev;
        return { ...prev, llm: next };
      });
    },
  });

  const embeddingMutation = useMutation({
    mutationFn: updateEmbeddingConfig,
    onSuccess: (next) => {
      setEmbeddingDraft(toEmbeddingDraft(next));
      queryClient.setQueryData(["models-config"], (prev: any) => {
        if (!prev) return prev;
        return { ...prev, embedding: next };
      });
    },
  });

  const resetLLMMutation = useMutation({
    mutationFn: resetLLMConfig,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["models-config"] });
    },
  });

  const resetEmbeddingMutation = useMutation({
    mutationFn: resetEmbeddingConfig,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["models-config"] });
    },
  });

  const llmProviders = useMemo(() => {
    const providers = availableQuery.data?.llm.providers ?? ["qwen", "zhipu"];
    return providers.filter((provider) => provider === "qwen" || provider === "zhipu");
  }, [availableQuery.data]);

  const embeddingProviders = useMemo(() => {
    const providers = availableQuery.data?.embedding.providers ?? ["qwen3-embedding", "zhipu"];
    return providers.filter((provider) => provider === "qwen3-embedding" || provider === "zhipu");
  }, [availableQuery.data]);

  const llmPresetMap = useMemo(() => {
    const entries = availableQuery.data?.llm.presets ?? [];
    const map = new Map<string, string>();
    for (const item of entries) {
      map.set(item.name, inferProviderByPreset(item.name, item.label));
    }
    return map;
  }, [availableQuery.data]);

  const localEmbeddingModels = availableQuery.data?.embedding.local_models ?? [];

  const loading = configQuery.isLoading || availableQuery.isLoading || !llmDraft || !embeddingDraft;

  const disabledByFeatureFlag =
    configQuery.error instanceof ApiError &&
    (configQuery.error.status === 404 || configQuery.error.status === 405);

  const actionError =
    llmMutation.error ||
    embeddingMutation.error ||
    resetLLMMutation.error ||
    resetEmbeddingMutation.error ||
    configQuery.error ||
    availableQuery.error;

  const actionErrorMessage = actionError instanceof Error ? actionError.message : null;

  const commitLLM = (next: LLMDraft) => {
    llmMutation.mutate({
      provider: next.provider,
      model: next.model.trim(),
      temperature: next.temperature,
      max_tokens: next.max_tokens,
      top_p: next.top_p,
    });
  };

  const queueModelCommit = (next: LLMDraft) => {
    if (modelDebounceRef.current) {
      clearTimeout(modelDebounceRef.current);
    }
    modelDebounceRef.current = setTimeout(() => {
      commitLLM(next);
    }, 300);
  };

  const commitEmbedding = (next: EmbeddingDraft) => {
    embeddingMutation.mutate({
      provider: next.provider,
      mode: next.mode ?? undefined,
      api_model: next.api_model,
    });
  };

  if (disabledByFeatureFlag) {
    return (
      <div className="control-panel-card">
        <div className="control-panel-card-title">{t(uiStrings.controlPanel.model)}</div>
        <div className="control-panel-card-hint">{t(uiStrings.controlPanel.modelFeatureDisabled)}</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="control-panel-card">
        <div className="control-panel-card-title">{t(uiStrings.controlPanel.model)}</div>
        <div className="control-panel-card-hint">{t(uiStrings.common.loading)}</div>
      </div>
    );
  }

  return (
    <div className="control-panel-stack">
      {actionErrorMessage ? (
        <div className="control-panel-error">{t(uiStrings.controlPanel.configSaveFailed)}: {actionErrorMessage}</div>
      ) : null}

      <div className="control-panel-card">
        <div className="control-panel-card-header">
          <div className="control-panel-card-title">{t(uiStrings.controlPanel.llmConfig)}</div>
          <button
            type="button"
            className="control-panel-reset-btn"
            onClick={() => {
              if (!window.confirm(t(uiStrings.controlPanel.restoreDefaultsConfirm))) return;
              resetLLMMutation.mutate();
            }}
            disabled={resetLLMMutation.isPending}
          >
            {t(uiStrings.controlPanel.restoreDefaults)}
          </button>
        </div>

        <div className="control-panel-card-body control-panel-stack">
          <div className="control-panel-field">
            <div className="control-panel-field-label">{t(uiStrings.controlPanel.llmProvider)}</div>
            <SegmentedControl
              value={llmDraft.provider}
              options={llmProviders.map((provider) => ({ value: provider, label: provider }))}
              onChange={(provider) => {
                const next = {
                  ...llmDraft,
                  provider,
                };
                setLlmDraft(next);
                commitLLM(next);
              }}
            />
          </div>

          <div className="control-panel-field">
            <label className="control-panel-field-label" htmlFor="llm-model-input">
              {t(uiStrings.controlPanel.llmModel)}
            </label>
            <input
              id="llm-model-input"
              className="input"
              list="llm-model-presets"
              value={llmDraft.model}
              onChange={(event) => {
                const rawModel = event.target.value;
                const matchedProvider = llmPresetMap.get(rawModel.trim());
                const next = {
                  ...llmDraft,
                  model: rawModel,
                  provider: matchedProvider || llmDraft.provider,
                };
                setLlmDraft(next);
                queueModelCommit(next);
              }}
              onBlur={() => {
                commitLLM(llmDraft);
              }}
            />
            <datalist id="llm-model-presets">
              {(availableQuery.data?.llm.presets ?? []).map((preset) => (
                <option key={preset.name} value={preset.name} label={preset.label} />
              ))}
            </datalist>
            <div className="control-panel-field-note">{t(uiStrings.controlPanel.llmModelHint)}</div>
          </div>

          <div className="control-panel-field">
            <div className="control-panel-field-row">
              <span className="control-panel-field-label">{t(uiStrings.controlPanel.temperature)}</span>
              <span className="control-panel-slider-value">{formatFloat(llmDraft.temperature)}</span>
            </div>
            <input
              className="control-panel-slider"
              type="range"
              min={0}
              max={2}
              step={0.05}
              value={llmDraft.temperature}
              onChange={(event) => {
                setLlmDraft({ ...llmDraft, temperature: Number(event.target.value) });
              }}
              onMouseUp={() => commitLLM(llmDraft)}
              onTouchEnd={() => commitLLM(llmDraft)}
            />
          </div>

          <div className="control-panel-field">
            <label className="control-panel-field-label" htmlFor="llm-max-tokens-input">
              {t(uiStrings.controlPanel.maxTokens)}
            </label>
            <input
              id="llm-max-tokens-input"
              className="input"
              type="number"
              min={1}
              max={131072}
              step={1024}
              value={llmDraft.max_tokens}
              onChange={(event) => {
                const raw = Number(event.target.value);
                const next = Number.isFinite(raw) && raw > 0 ? raw : llmDraft.max_tokens;
                setLlmDraft({ ...llmDraft, max_tokens: next });
              }}
              onBlur={() => commitLLM(llmDraft)}
            />
          </div>

          <div className="control-panel-field">
            <div className="control-panel-field-row">
              <span className="control-panel-field-label">{t(uiStrings.controlPanel.topP)}</span>
              <span className="control-panel-slider-value">{formatFloat(llmDraft.top_p)}</span>
            </div>
            <input
              className="control-panel-slider"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={llmDraft.top_p}
              onChange={(event) => {
                setLlmDraft({ ...llmDraft, top_p: Number(event.target.value) });
              }}
              onMouseUp={() => commitLLM(llmDraft)}
              onTouchEnd={() => commitLLM(llmDraft)}
            />
          </div>
        </div>
      </div>

      <div className="control-panel-card">
        <div className="control-panel-card-header">
          <div className="control-panel-card-title">{t(uiStrings.controlPanel.embeddingConfig)}</div>
          <button
            type="button"
            className="control-panel-reset-btn"
            onClick={() => {
              if (!window.confirm(t(uiStrings.controlPanel.restoreDefaultsConfirm))) return;
              resetEmbeddingMutation.mutate();
            }}
            disabled={resetEmbeddingMutation.isPending}
          >
            {t(uiStrings.controlPanel.restoreDefaults)}
          </button>
        </div>

        <div className="control-panel-card-body control-panel-stack">
          <div className="control-panel-field">
            <div className="control-panel-field-label">{t(uiStrings.controlPanel.embeddingProvider)}</div>
            <SegmentedControl
              value={embeddingDraft.provider}
              options={embeddingProviders.map((provider) => ({ value: provider, label: provider }))}
              onChange={(provider) => {
                if (provider === embeddingDraft.provider) return;
                if (!window.confirm(t(uiStrings.controlPanel.embeddingSwitchConfirm))) return;

                if (provider === "qwen3-embedding") {
                  const next = {
                    ...embeddingDraft,
                    provider,
                    mode: embeddingDraft.mode || "api",
                    api_model: embeddingDraft.api_model || "text-embedding-v4",
                    model: embeddingDraft.api_model || "text-embedding-v4",
                  };
                  setEmbeddingDraft(next);
                  commitEmbedding(next);
                  return;
                }

                const next = {
                  ...embeddingDraft,
                  provider,
                  mode: null,
                  api_model: "embedding-3",
                  model: "embedding-3",
                };
                setEmbeddingDraft(next);
                commitEmbedding(next);
              }}
            />
          </div>

          {embeddingDraft.provider === "qwen3-embedding" ? (
            <>
              <div className="control-panel-field">
                <div className="control-panel-field-label">{t(uiStrings.controlPanel.embeddingMode)}</div>
                <SegmentedControl
                  value={embeddingDraft.mode || "api"}
                  options={[
                    { value: "local", label: t(uiStrings.controlPanel.embeddingModeLocal) },
                    { value: "api", label: t(uiStrings.controlPanel.embeddingModeApi) },
                  ]}
                  onChange={(mode) => {
                    if (mode === embeddingDraft.mode) return;
                    if (!window.confirm(t(uiStrings.controlPanel.embeddingSwitchConfirm))) return;

                    const next = {
                      ...embeddingDraft,
                      mode,
                      model:
                        mode === "local"
                          ? localEmbeddingModels[0] || embeddingDraft.model
                          : embeddingDraft.api_model,
                    };
                    setEmbeddingDraft(next);
                    commitEmbedding(next);
                  }}
                />
              </div>

              {(embeddingDraft.mode || "api") === "api" ? (
                <div className="control-panel-field">
                  <label className="control-panel-field-label" htmlFor="embedding-api-model-input">
                    {t(uiStrings.controlPanel.embeddingModel)}
                  </label>
                  <input
                    id="embedding-api-model-input"
                    className="input"
                    list="embedding-api-models"
                    value={embeddingDraft.api_model}
                    onChange={(event) => {
                      const value = event.target.value;
                      setEmbeddingDraft({
                        ...embeddingDraft,
                        api_model: value,
                        model: value,
                      });
                    }}
                    onBlur={() => {
                      commitEmbedding(embeddingDraft);
                    }}
                  />
                  <datalist id="embedding-api-models">
                    {(availableQuery.data?.embedding.api_models ?? []).map((preset) => (
                      <option key={preset.name} value={preset.name} label={preset.label} />
                    ))}
                  </datalist>
                </div>
              ) : (
                <div className="control-panel-readonly-row">
                  <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.embeddingModel)}</span>
                  <span>{localEmbeddingModels[0] || embeddingDraft.model}</span>
                </div>
              )}
            </>
          ) : (
            <div className="control-panel-readonly-row">
              <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.embeddingModel)}</span>
              <span>{embeddingDraft.model}</span>
            </div>
          )}

          <div className="control-panel-readonly-row">
            <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.embeddingDim)}</span>
            <span>{embeddingDraft.dim}</span>
          </div>

          <div className="control-panel-warning">{t(uiStrings.controlPanel.embeddingSwitchWarning)}</div>
        </div>
      </div>
    </div>
  );
}
