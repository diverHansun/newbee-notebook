import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const apiMocks = vi.hoisted(() => ({
  getAvailableModels: vi.fn(),
  getModelsConfig: vi.fn(),
  resetASRConfig: vi.fn(),
  resetEmbeddingConfig: vi.fn(),
  resetLLMConfig: vi.fn(),
  resetMinerUConfig: vi.fn(),
  updateASRConfig: vi.fn(),
  updateEmbeddingConfig: vi.fn(),
  updateLLMConfig: vi.fn(),
  updateMinerUConfig: vi.fn(),
}));

vi.mock("@/lib/api/config", () => ({
  getAvailableModels: () => apiMocks.getAvailableModels(),
  getModelsConfig: () => apiMocks.getModelsConfig(),
  resetASRConfig: () => apiMocks.resetASRConfig(),
  resetEmbeddingConfig: () => apiMocks.resetEmbeddingConfig(),
  resetLLMConfig: () => apiMocks.resetLLMConfig(),
  resetMinerUConfig: () => apiMocks.resetMinerUConfig(),
  updateASRConfig: (...args: unknown[]) => apiMocks.updateASRConfig(...args),
  updateEmbeddingConfig: (...args: unknown[]) => apiMocks.updateEmbeddingConfig(...args),
  updateLLMConfig: (...args: unknown[]) => apiMocks.updateLLMConfig(...args),
  updateMinerUConfig: (...args: unknown[]) => apiMocks.updateMinerUConfig(...args),
}));

import { ModelConfigPanel } from "@/components/layout/model-config-panel";

function renderPanel(ui: ReactNode) {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>{ui}</LanguageContext.Provider>
    </QueryClientProvider>
  );
}

function buildModelsConfig(overrides?: {
  llm?: Partial<{
    provider: string;
    model: string;
    temperature: number;
    max_tokens: number;
    top_p: number;
    source: string;
    api_key_set: boolean;
  }>;
  embedding?: Partial<{
    provider: string;
    mode: string | null;
    model: string;
    dim: number;
    source: string;
    api_key_set: boolean | null;
  }>;
  mineru?: Partial<{
    mode: string;
    source: string;
    local_enabled: boolean;
    api_key_set: boolean | null;
  }>;
  asr?: Partial<{
    provider: string;
    model: string;
    source: string;
    api_key_set: boolean;
  }>;
}) {
  return {
    llm: {
      provider: "qwen",
      model: "qwen3.5-plus",
      temperature: 0.7,
      max_tokens: 8192,
      top_p: 0.9,
      source: "db",
      api_key_set: true,
      ...overrides?.llm,
    },
    embedding: {
      provider: "qwen3-embedding",
      mode: "api",
      model: "text-embedding-v4",
      dim: 1024,
      source: "db",
      api_key_set: true,
      ...overrides?.embedding,
    },
    mineru: {
      mode: "cloud",
      source: "db",
      local_enabled: true,
      api_key_set: true,
      ...overrides?.mineru,
    },
    asr: {
      provider: "zhipu",
      model: "glm-asr-2512",
      source: "db",
      api_key_set: true,
      ...overrides?.asr,
    },
  };
}

function buildAvailableModels() {
  return {
    llm: {
      providers: ["qwen", "zhipu"],
      presets: [
        { name: "qwen3.5-plus", label: "Qwen3.5 Plus" },
        { name: "glm-4.7", label: "GLM 4.7" },
      ],
      custom_input: true,
    },
    embedding: {
      providers: ["qwen3-embedding", "zhipu"],
      modes: ["api", "local"],
      api_models: [{ name: "text-embedding-v4", label: "text-embedding-v4" }],
      local_models: ["gte-Qwen2-7B-instruct-Q4_K_M.gguf"],
    },
    mineru: {
      modes: ["cloud", "local"],
    },
    asr: {
      providers: ["zhipu", "qwen"],
      presets: [
        { name: "glm-asr-2512", label: "GLM-ASR (Zhipu)" },
        { name: "qwen3-asr-flash", label: "Qwen3-ASR-Flash (Qwen)" },
      ],
    },
  };
}

describe("ModelConfigPanel", () => {
  beforeEach(() => {
    apiMocks.getModelsConfig.mockReset();
    apiMocks.getAvailableModels.mockReset();
    apiMocks.updateLLMConfig.mockReset();
    apiMocks.updateEmbeddingConfig.mockReset();
    apiMocks.updateASRConfig.mockReset();
    apiMocks.updateMinerUConfig.mockReset();
    apiMocks.resetLLMConfig.mockReset();
    apiMocks.resetEmbeddingConfig.mockReset();
    apiMocks.resetASRConfig.mockReset();
    apiMocks.resetMinerUConfig.mockReset();

    apiMocks.getModelsConfig.mockResolvedValue(buildModelsConfig());
    apiMocks.getAvailableModels.mockResolvedValue(buildAvailableModels());
    apiMocks.updateLLMConfig.mockResolvedValue(buildModelsConfig().llm);
    apiMocks.updateEmbeddingConfig.mockResolvedValue(buildModelsConfig().embedding);
    apiMocks.updateASRConfig.mockResolvedValue(buildModelsConfig().asr);
    apiMocks.updateMinerUConfig.mockResolvedValue(buildModelsConfig().mineru);
    apiMocks.resetLLMConfig.mockResolvedValue({ message: "ok", defaults: {} });
    apiMocks.resetEmbeddingConfig.mockResolvedValue({ message: "ok", defaults: {} });
    apiMocks.resetASRConfig.mockResolvedValue({ message: "ok", defaults: {} });
    apiMocks.resetMinerUConfig.mockResolvedValue({ message: "ok", defaults: {} });

    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  it("shows asr api key warning when the selected provider is not configured", async () => {
    apiMocks.getModelsConfig.mockResolvedValue(
      buildModelsConfig({
        asr: {
          provider: "qwen",
          model: "qwen3-asr-flash",
          api_key_set: false,
        },
      })
    );

    renderPanel(<ModelConfigPanel />);

    const asrHeading = await screen.findByText("ASR Configuration");
    const asrCard = asrHeading.closest(".control-panel-card");
    expect(asrCard).not.toBeNull();

    expect(within(asrCard as HTMLElement).getByDisplayValue("qwen3-asr-flash")).toBeInTheDocument();
    expect(within(asrCard as HTMLElement).getAllByText(/configure qwen api key/i)).toHaveLength(2);
  });

  it("shows llm api key status for configured and missing states", async () => {
    apiMocks.getModelsConfig.mockResolvedValueOnce(buildModelsConfig()).mockResolvedValueOnce(
      buildModelsConfig({
        llm: {
          api_key_set: false,
        },
      })
    );

    const { unmount } = renderPanel(<ModelConfigPanel />);

    const llmHeading = await screen.findByText("LLM Configuration");
    const llmCard = llmHeading.closest(".control-panel-card");
    expect(llmCard).not.toBeNull();
    expect(within(llmCard as HTMLElement).getByText("API key")).toBeInTheDocument();
    expect(within(llmCard as HTMLElement).getByText("API key configured")).toBeInTheDocument();

    unmount();
    renderPanel(<ModelConfigPanel />);

    const llmHeadingWithMissingKey = await screen.findByText("LLM Configuration");
    const llmCardWithMissingKey = llmHeadingWithMissingKey.closest(".control-panel-card");
    expect(llmCardWithMissingKey).not.toBeNull();
    expect(within(llmCardWithMissingKey as HTMLElement).getByText("API key not configured")).toBeInTheDocument();
  });

  it("hides embedding api key status when current mode does not require key", async () => {
    apiMocks.getModelsConfig.mockResolvedValue(
      buildModelsConfig({
        embedding: {
          mode: "local",
          api_key_set: null,
        },
      })
    );

    renderPanel(<ModelConfigPanel />);

    const embeddingHeading = await screen.findByText("Embedding Configuration");
    const embeddingCard = embeddingHeading.closest(".control-panel-card");
    expect(embeddingCard).not.toBeNull();
    expect(within(embeddingCard as HTMLElement).queryByText("API key")).not.toBeInTheDocument();
  });

  it("hides mineru api key status when current mode does not require key", async () => {
    apiMocks.getModelsConfig.mockResolvedValue(
      buildModelsConfig({
        mineru: {
          mode: "local",
          api_key_set: null,
        },
      })
    );

    renderPanel(<ModelConfigPanel />);

    const mineruHeading = await screen.findByText("MinerU Configuration");
    const mineruCard = mineruHeading.closest(".control-panel-card");
    expect(mineruCard).not.toBeNull();
    expect(within(mineruCard as HTMLElement).queryByText("API key")).not.toBeInTheDocument();
  });

  it("updates the asr provider with the provider default model", async () => {
    const user = userEvent.setup();
    apiMocks.updateASRConfig.mockResolvedValue({
      provider: "qwen",
      model: "qwen3-asr-flash",
      source: "db",
      api_key_set: true,
    });

    renderPanel(<ModelConfigPanel />);

    const asrHeading = await screen.findByText("ASR Configuration");
    const asrCard = asrHeading.closest(".control-panel-card");
    expect(asrCard).not.toBeNull();

    await user.click(within(asrCard as HTMLElement).getByRole("radio", { name: "qwen" }));

    await waitFor(() => {
      expect(apiMocks.updateASRConfig).toHaveBeenCalledWith({
        provider: "qwen",
        model: "qwen3-asr-flash",
      }, expect.anything());
    });
    expect(within(asrCard as HTMLElement).getByDisplayValue("qwen3-asr-flash")).toBeInTheDocument();
  });

  it("resets asr configuration from the model settings panel", async () => {
    const user = userEvent.setup();
    renderPanel(<ModelConfigPanel />);

    const asrHeading = await screen.findByText("ASR Configuration");
    const asrCard = asrHeading.closest(".control-panel-card");
    expect(asrCard).not.toBeNull();

    await user.click(within(asrCard as HTMLElement).getByRole("button", { name: "Restore Defaults" }));

    await waitFor(() => {
      expect(apiMocks.resetASRConfig).toHaveBeenCalledOnce();
    });
  });

  it("updates mineru mode from cloud to local", async () => {
    const user = userEvent.setup();
    apiMocks.updateMinerUConfig.mockResolvedValue({
      mode: "local",
      source: "db",
      local_enabled: true,
      api_key_set: null,
    });

    renderPanel(<ModelConfigPanel />);

    const mineruHeading = await screen.findByText("MinerU Configuration");
    const mineruCard = mineruHeading.closest(".control-panel-card");
    expect(mineruCard).not.toBeNull();

    await user.click(within(mineruCard as HTMLElement).getByRole("radio", { name: "Local" }));

    await waitFor(() => {
      expect(apiMocks.updateMinerUConfig).toHaveBeenCalled();
    });
    expect(apiMocks.updateMinerUConfig.mock.calls[0][0]).toEqual({ mode: "local" });
  });
});
