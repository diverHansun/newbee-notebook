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
  updateASRConfig: vi.fn(),
  updateEmbeddingConfig: vi.fn(),
  updateLLMConfig: vi.fn(),
}));

vi.mock("@/lib/api/config", () => ({
  getAvailableModels: () => apiMocks.getAvailableModels(),
  getModelsConfig: () => apiMocks.getModelsConfig(),
  resetASRConfig: () => apiMocks.resetASRConfig(),
  resetEmbeddingConfig: () => apiMocks.resetEmbeddingConfig(),
  resetLLMConfig: () => apiMocks.resetLLMConfig(),
  updateASRConfig: (...args: unknown[]) => apiMocks.updateASRConfig(...args),
  updateEmbeddingConfig: (...args: unknown[]) => apiMocks.updateEmbeddingConfig(...args),
  updateLLMConfig: (...args: unknown[]) => apiMocks.updateLLMConfig(...args),
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
    },
    embedding: {
      provider: "qwen3-embedding",
      mode: "api",
      model: "text-embedding-v4",
      dim: 1024,
      source: "db",
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
    apiMocks.resetLLMConfig.mockReset();
    apiMocks.resetEmbeddingConfig.mockReset();
    apiMocks.resetASRConfig.mockReset();

    apiMocks.getModelsConfig.mockResolvedValue(buildModelsConfig());
    apiMocks.getAvailableModels.mockResolvedValue(buildAvailableModels());
    apiMocks.updateLLMConfig.mockResolvedValue(buildModelsConfig().llm);
    apiMocks.updateEmbeddingConfig.mockResolvedValue(buildModelsConfig().embedding);
    apiMocks.updateASRConfig.mockResolvedValue(buildModelsConfig().asr);
    apiMocks.resetLLMConfig.mockResolvedValue({ message: "ok", defaults: {} });
    apiMocks.resetEmbeddingConfig.mockResolvedValue({ message: "ok", defaults: {} });
    apiMocks.resetASRConfig.mockResolvedValue({ message: "ok", defaults: {} });

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
});
