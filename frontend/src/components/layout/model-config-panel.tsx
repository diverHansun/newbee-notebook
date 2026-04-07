"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  getAvailableModels,
  getModelsConfig,
  resetASRConfig,
  resetEmbeddingConfig,
  resetLLMConfig,
  resetMinerUConfig,
  updateASRConfig,
  updateEmbeddingConfig,
  updateLLMConfig,
  updateMinerUConfig,
  type ASRConfig,
  type EmbeddingConfig,
  type LLMConfig,
  type MinerUConfig,
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
  api_key_set: boolean;
};

type EmbeddingDraft = {
  provider: string;
  mode: string | null;
  api_provider: string;
  api_model: string;
  model: string;
  dim: number;
  api_key_set: boolean | null;
};

type ASRDraft = {
  provider: string;
  model: string;
  api_key_set: boolean;
};

type MinerUDraft = {
  mode: string;
  source: string;
  local_enabled: boolean;
  api_key_set: boolean | null;
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
function getDefaultLLMModel(provider: string, presets: Array<{ name: string; label: string }>): string {
  const fallback = provider === "zhipu" ? "glm-5" : "qwen3.5-plus";
  const matchedPreset = presets.find((item) => inferProviderByPreset(item.name, item.label) === provider);
  return matchedPreset?.name ?? fallback;
}

function getDefaultASRModel(provider: string, presets: Array<{ name: string; label: string }>): string {
  const fallback = provider === "zhipu" ? "glm-asr-2512" : "qwen3-asr-flash";
  const matchedPreset = presets.find((item) => inferProviderByPreset(item.name, item.label) === provider);
  return matchedPreset?.name ?? fallback;
}

function inferEmbeddingApiProvider(provider: string | null | undefined): string {
  return provider === "zhipu" ? "zhipu" : "qwen";
}

function getDefaultEmbeddingApiModel(
  apiProvider: string,
  presetsByProvider: Record<string, Array<{ name: string; label: string }>>
): string {
  const presets = presetsByProvider[apiProvider] ?? [];
  if (presets.length > 0) {
    return presets[0].name;
  }
  return apiProvider === "zhipu" ? "embedding-3" : "text-embedding-v4";
}

function toLLMDraft(config: LLMConfig): LLMDraft {
  return {
    provider: config.provider,
    model: config.model,
    temperature: config.temperature,
    max_tokens: config.max_tokens,
    top_p: config.top_p,
    api_key_set: config.api_key_set,
  };
}

function toEmbeddingDraft(config: EmbeddingConfig): EmbeddingDraft {
  return {
    provider: config.provider,
    mode: config.mode,
    api_provider: config.api_provider ?? inferEmbeddingApiProvider(config.provider),
    api_model: config.api_model ?? config.model,
    model: config.model,
    dim: config.dim,
    api_key_set: config.api_key_set,
  };
}

function toASRDraft(config: ASRConfig): ASRDraft {
  return {
    provider: config.provider,
    model: config.model,
    api_key_set: config.api_key_set,
  };
}

function toMinerUDraft(config: MinerUConfig): MinerUDraft {
  return {
    mode: config.mode,
    source: config.source,
    local_enabled: config.local_enabled,
    api_key_set: config.api_key_set,
  };
}

export function ModelConfigPanel() {
  const { t, ti } = useLang();
  const queryClient = useQueryClient();

  const [llmDraft, setLlmDraft] = useState<LLMDraft | null>(null);
  const [embeddingDraft, setEmbeddingDraft] = useState<EmbeddingDraft | null>(null);
  const [asrDraft, setAsrDraft] = useState<ASRDraft | null>(null);
  const [mineruDraft, setMineruDraft] = useState<MinerUDraft | null>(null);

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
    setAsrDraft(toASRDraft(configQuery.data.asr));
    setMineruDraft(toMinerUDraft(configQuery.data.mineru));
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

  const mineruMutation = useMutation({
    mutationFn: updateMinerUConfig,
    onSuccess: (next) => {
      setMineruDraft(toMinerUDraft(next));
      queryClient.setQueryData(["models-config"], (prev: any) => {
        if (!prev) return prev;
        return { ...prev, mineru: next };
      });
    },
  });

  const resetMinerUMutation = useMutation({
    mutationFn: resetMinerUConfig,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["models-config"] });
    },
  });

  const asrMutation = useMutation({
    mutationFn: updateASRConfig,
    onSuccess: (next) => {
      setAsrDraft(toASRDraft(next));
      queryClient.setQueryData(["models-config"], (prev: any) => {
        if (!prev) return prev;
        return { ...prev, asr: next };
      });
    },
  });

  const resetAsrMutation = useMutation({
    mutationFn: resetASRConfig,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["models-config"] });
    },
  });

  const llmProviders = useMemo(() => {
    const providers = availableQuery.data?.llm.providers ?? ["qwen", "zhipu"];
    return providers.filter((provider) => provider === "qwen" || provider === "zhipu");
  }, [availableQuery.data]);

  const embeddingApiProviders = useMemo(() => {
    const providers = availableQuery.data?.embedding.api_providers ?? ["qwen", "zhipu"];
    return providers.filter((provider) => provider === "qwen" || provider === "zhipu");
  }, [availableQuery.data]);

  const embeddingApiModelsByProvider = useMemo(() => {
    return availableQuery.data?.embedding.api_models_by_provider ?? {
      qwen: [{ name: "text-embedding-v4", label: "text-embedding-v4" }],
      zhipu: [{ name: "embedding-3", label: "embedding-3" }],
    };
  }, [availableQuery.data]);

  const asrProviders = useMemo(() => {
    const providers = availableQuery.data?.asr.providers ?? ["zhipu", "qwen"];
    return providers.filter((provider) => provider === "qwen" || provider === "zhipu");
  }, [availableQuery.data]);

  const llmPresetMap = useMemo(() => {
    const entries = availableQuery.data?.llm.presets ?? [];
    const map = new Map<string, string>();
    for (const item of entries) {
      map.set(item.name, inferProviderByPreset(item.name, item.label));
    }
    return map;
  }, [availableQuery.data]);

  const asrPresetMap = useMemo(() => {
    const entries = availableQuery.data?.asr.presets ?? [];
    const map = new Map<string, string>();
    for (const item of entries) {
      map.set(item.name, inferProviderByPreset(item.name, item.label));
    }
    return map;
  }, [availableQuery.data]);

  const localEmbeddingModels = availableQuery.data?.embedding.local_models ?? [];
  const currentEmbeddingApiModels = embeddingApiModelsByProvider[embeddingDraft?.api_provider ?? "qwen"] ?? [];
  const mineruModes =
    availableQuery.data?.mineru?.modes ?? (mineruDraft?.local_enabled ? ["cloud", "local"] : ["cloud"]);

  const loading =
    configQuery.isLoading ||
    availableQuery.isLoading ||
    !llmDraft ||
    !embeddingDraft ||
    !asrDraft ||
    !mineruDraft;

  const disabledByFeatureFlag =
    configQuery.error instanceof ApiError &&
    (configQuery.error.status === 404 || configQuery.error.status === 405);

  const actionError =
    llmMutation.error ||
    embeddingMutation.error ||
    mineruMutation.error ||
    asrMutation.error ||
    resetLLMMutation.error ||
    resetEmbeddingMutation.error ||
    resetMinerUMutation.error ||
    resetAsrMutation.error ||
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
      mode: next.mode ?? undefined,
      api_provider: next.api_provider,
      api_model: next.api_model,
    });
  };

  const commitASR = (next: ASRDraft) => {
    asrMutation.mutate({
      provider: next.provider,
      model: next.model.trim(),
    });
  };

  const commitMinerU = (next: MinerUDraft) => {
    mineruMutation.mutate({
      mode: next.mode,
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
                if (provider === llmDraft.provider) return;
                const llmPresets = availableQuery.data?.llm.presets ?? [];
                const next = {
                  ...llmDraft,
                  provider,
                  model: getDefaultLLMModel(provider, llmPresets),
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

          {llmDraft.api_key_set !== null ? (
            <div className="control-panel-readonly-row">
              <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.apiKeyStatus)}</span>
              <span className="control-panel-status">
                <span
                  className={`control-panel-status-dot${llmDraft.api_key_set ? " is-ok" : ""}`}
                  aria-hidden="true"
                />
                <span>
                  {llmDraft.api_key_set
                    ? t(uiStrings.controlPanel.apiKeyConfigured)
                    : t(uiStrings.controlPanel.apiKeyMissing)}
                </span>
              </span>
            </div>
          ) : null}
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

                const nextApiModel =
                  mode === "local"
                    ? embeddingDraft.api_model
                    : embeddingDraft.api_model ||
                      getDefaultEmbeddingApiModel(embeddingDraft.api_provider, embeddingApiModelsByProvider);
                const next = {
                  ...embeddingDraft,
                  provider: mode === "local" ? "qwen3-embedding" : (embeddingDraft.api_provider === "zhipu" ? "zhipu" : "qwen3-embedding"),
                  mode,
                  api_model: nextApiModel,
                  model: mode === "local" ? localEmbeddingModels[0] || embeddingDraft.model : nextApiModel,
                };
                setEmbeddingDraft(next);
                commitEmbedding(next);
              }}
            />
          </div>

          {(embeddingDraft.mode || "api") === "api" ? (
            <>
              <div className="control-panel-field">
                <div className="control-panel-field-label">{t(uiStrings.controlPanel.embeddingProvider)}</div>
                <SegmentedControl
                  value={embeddingDraft.api_provider}
                  options={embeddingApiProviders.map((provider) => ({ value: provider, label: provider }))}
                  onChange={(apiProvider) => {
                    if (apiProvider === embeddingDraft.api_provider) return;
                    if (!window.confirm(t(uiStrings.controlPanel.embeddingSwitchConfirm))) return;

                    const nextApiModel = getDefaultEmbeddingApiModel(apiProvider, embeddingApiModelsByProvider);
                    const next = {
                      ...embeddingDraft,
                      provider: apiProvider === "zhipu" ? "zhipu" : "qwen3-embedding",
                      mode: "api",
                      api_provider: apiProvider,
                      api_model: nextApiModel,
                      model: nextApiModel,
                    };
                    setEmbeddingDraft(next);
                    commitEmbedding(next);
                  }}
                />
              </div>

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
                  {currentEmbeddingApiModels.map((preset) => (
                    <option key={preset.name} value={preset.name} label={preset.label} />
                  ))}
                </datalist>
              </div>
            </>
          ) : (
            <div className="control-panel-readonly-row">
              <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.embeddingModel)}</span>
              <span>{localEmbeddingModels[0] || embeddingDraft.model}</span>
            </div>
          )}

          <div className="control-panel-readonly-row">
            <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.embeddingDim)}</span>
            <span>{embeddingDraft.dim}</span>
          </div>

          {embeddingDraft.api_key_set !== null ? (
            <div className="control-panel-readonly-row">
              <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.apiKeyStatus)}</span>
              <span className="control-panel-status">
                <span
                  className={`control-panel-status-dot${embeddingDraft.api_key_set ? " is-ok" : ""}`}
                  aria-hidden="true"
                />
                <span>
                  {embeddingDraft.api_key_set
                    ? t(uiStrings.controlPanel.apiKeyConfigured)
                    : t(uiStrings.controlPanel.apiKeyMissing)}
                </span>
              </span>
            </div>
          ) : null}

          <div className="control-panel-warning">{t(uiStrings.controlPanel.embeddingSwitchWarning)}</div>
        </div>
      </div>

      <div className="control-panel-card">
        <div className="control-panel-card-header">
          <div className="control-panel-card-title">{t(uiStrings.controlPanel.asrConfig)}</div>
          <button
            type="button"
            className="control-panel-reset-btn"
            onClick={() => {
              if (!window.confirm(t(uiStrings.controlPanel.restoreDefaultsConfirm))) return;
              resetAsrMutation.mutate();
            }}
            disabled={resetAsrMutation.isPending}
          >
            {t(uiStrings.controlPanel.restoreDefaults)}
          </button>
        </div>

        <div className="control-panel-card-body control-panel-stack">
          <div className="control-panel-field">
            <div className="control-panel-field-label">{t(uiStrings.controlPanel.asrProvider)}</div>
            <SegmentedControl
              value={asrDraft.provider}
              options={asrProviders.map((provider) => ({ value: provider, label: provider }))}
              onChange={(provider) => {
                if (provider === asrDraft.provider) return;
                const asrPresets = availableQuery.data?.asr.presets ?? [];
                const next = {
                  ...asrDraft,
                  provider,
                  model: getDefaultASRModel(provider, asrPresets),
                };
                setAsrDraft(next);
                commitASR(next);
              }}
            />
          </div>

          <div className="control-panel-field">
            <label className="control-panel-field-label" htmlFor="asr-model-input">
              {t(uiStrings.controlPanel.asrModel)}
            </label>
            <input
              id="asr-model-input"
              className="input"
              list="asr-model-presets"
              value={asrDraft.model}
              onChange={(event) => {
                const rawModel = event.target.value;
                const matchedProvider = asrPresetMap.get(rawModel.trim());
                setAsrDraft({
                  ...asrDraft,
                  model: rawModel,
                  provider: matchedProvider || asrDraft.provider,
                });
              }}
              onBlur={() => {
                commitASR(asrDraft);
              }}
            />
            <datalist id="asr-model-presets">
              {(availableQuery.data?.asr.presets ?? []).map((preset) => (
                <option key={preset.name} value={preset.name} label={preset.label} />
              ))}
            </datalist>
            <div className="control-panel-field-note">{t(uiStrings.controlPanel.asrModelHint)}</div>
          </div>

          <div className="control-panel-readonly-row">
            <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.asrApiKeyStatus)}</span>
            <span className="control-panel-status">
              <span
                className={`control-panel-status-dot${asrDraft.api_key_set ? " is-ok" : ""}`}
                aria-hidden="true"
              />
              <span>
                {asrDraft.api_key_set
                  ? t(uiStrings.controlPanel.asrApiKeyConfigured)
                  : ti(uiStrings.controlPanel.asrApiKeyMissing, { provider: asrDraft.provider })}
              </span>
            </span>
          </div>

          {!asrDraft.api_key_set ? (
            <div className="control-panel-warning">
              {ti(uiStrings.controlPanel.asrApiKeyMissing, { provider: asrDraft.provider })}
            </div>
          ) : null}
        </div>
      </div>

      <div className="control-panel-card">
        <div className="control-panel-card-header">
          <div className="control-panel-card-title">{t(uiStrings.controlPanel.mineruConfig)}</div>
          <button
            type="button"
            className="control-panel-reset-btn"
            onClick={() => {
              if (!window.confirm(t(uiStrings.controlPanel.restoreDefaultsConfirm))) return;
              resetMinerUMutation.mutate();
            }}
            disabled={resetMinerUMutation.isPending}
          >
            {t(uiStrings.controlPanel.restoreDefaults)}
          </button>
        </div>

        <div className="control-panel-card-body control-panel-stack">
          <div className="control-panel-field">
            <div className="control-panel-field-label">{t(uiStrings.controlPanel.mineruMode)}</div>
            <SegmentedControl
              value={mineruDraft.mode}
              options={mineruModes.map((mode) => ({
                value: mode,
                label:
                  mode === "local"
                    ? t(uiStrings.controlPanel.mineruModeLocal)
                    : t(uiStrings.controlPanel.mineruModeCloud),
              }))}
              onChange={(mode) => {
                if (mode === mineruDraft.mode) return;
                const next = {
                  ...mineruDraft,
                  mode,
                };
                setMineruDraft(next);
                commitMinerU(next);
              }}
            />
          </div>
          {mineruDraft.local_enabled ? (
            <div className="control-panel-field-note">{t(uiStrings.controlPanel.mineruModeHint)}</div>
          ) : (
            <div className="control-panel-warning">{t(uiStrings.controlPanel.mineruLocalDisabledHint)}</div>
          )}

          {mineruDraft.api_key_set !== null ? (
            <div className="control-panel-readonly-row">
              <span className="control-panel-readonly-label">{t(uiStrings.controlPanel.apiKeyStatus)}</span>
              <span className="control-panel-status">
                <span
                  className={`control-panel-status-dot${mineruDraft.api_key_set ? " is-ok" : ""}`}
                  aria-hidden="true"
                />
                <span>
                  {mineruDraft.api_key_set
                    ? t(uiStrings.controlPanel.apiKeyConfigured)
                    : t(uiStrings.controlPanel.apiKeyMissing)}
                </span>
              </span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
