import { apiFetch } from "@/lib/api/client";

export interface LLMConfig {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  source: string;
  api_key_set: boolean;
}

export interface EmbeddingConfig {
  provider: string;
  mode: string | null;
  api_provider?: string | null;
  model: string;
  api_model?: string | null;
  dim: number;
  source: string;
  api_key_set: boolean | null;
}

export interface ASRConfig {
  provider: string;
  model: string;
  source: string;
  api_key_set: boolean;
}

export interface MinerUConfig {
  mode: string;
  source: string;
  local_enabled: boolean;
  api_key_set: boolean | null;
}

export interface ModelsConfig {
  llm: LLMConfig;
  embedding: EmbeddingConfig;
  mineru: MinerUConfig;
  asr: ASRConfig;
}

export interface PresetModel {
  name: string;
  label: string;
}

export interface AvailableModels {
  llm: {
    providers: string[];
    presets: PresetModel[];
    custom_input: boolean;
  };
  embedding: {
    modes: string[];
    api_providers: string[];
    api_models_by_provider: Record<string, PresetModel[]>;
    local_models: string[];
  };
  mineru: {
    modes: string[];
  };
  asr: {
    providers: string[];
    presets: PresetModel[];
  };
}

export interface UpdateLLMPayload {
  provider: string;
  model: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
}

export interface UpdateEmbeddingPayload {
  mode?: string;
  provider?: string;
  api_provider?: string;
  api_model?: string;
}

export interface UpdateASRPayload {
  provider: string;
  model?: string;
}

export interface UpdateMinerUPayload {
  mode: string;
}

export interface ResetResponse {
  message: string;
  defaults: Record<string, unknown>;
}

export function getModelsConfig() {
  return apiFetch<ModelsConfig>("/config/models");
}

export function getAvailableModels() {
  return apiFetch<AvailableModels>("/config/models/available");
}

export function updateLLMConfig(payload: UpdateLLMPayload) {
  return apiFetch<LLMConfig>("/config/llm", {
    method: "PUT",
    body: payload,
  });
}

export function updateEmbeddingConfig(payload: UpdateEmbeddingPayload) {
  return apiFetch<EmbeddingConfig>("/config/embedding", {
    method: "PUT",
    body: payload,
  });
}

export function updateASRConfig(payload: UpdateASRPayload) {
  return apiFetch<ASRConfig>("/config/asr", {
    method: "PUT",
    body: payload,
  });
}

export function updateMinerUConfig(payload: UpdateMinerUPayload) {
  return apiFetch<MinerUConfig>("/config/mineru", {
    method: "PUT",
    body: payload,
  });
}

export function resetLLMConfig() {
  return apiFetch<ResetResponse>("/config/llm/reset", {
    method: "POST",
  });
}

export function resetEmbeddingConfig() {
  return apiFetch<ResetResponse>("/config/embedding/reset", {
    method: "POST",
  });
}

export function resetASRConfig() {
  return apiFetch<ResetResponse>("/config/asr/reset", {
    method: "POST",
  });
}

export function resetMinerUConfig() {
  return apiFetch<ResetResponse>("/config/mineru/reset", {
    method: "POST",
  });
}
