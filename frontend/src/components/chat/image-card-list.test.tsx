import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ImageCardList } from "@/components/chat/image-card-list";
import { renderWithLang } from "@/test/test-utils";

const longPrompt =
  "A cute honey bee illustration, warm color palette with golden yellows, soft oranges, and honey glow lighting for a friendly poster composition.";

describe("ImageCardList", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders a localized download icon link and removes extra prompt controls", () => {
    renderWithLang(
      <ImageCardList
        images={[
          {
            imageId: "img-1",
            storageKey: "generated-images/demo/img-1.png",
            prompt: longPrompt,
            provider: "zhipu",
            model: "glm-image",
            width: 1280,
            height: 1280,
          },
        ]}
      />,
      { lang: "en" }
    );

    fireEvent.load(screen.getByAltText("Generated image"));
    const downloadLink = screen.getByRole("link", { name: "Download image" });
    expect(downloadLink).toHaveAttribute("href", "/api/v1/generated-images/img-1/data?download=1");
    expect(screen.queryByText("View prompt")).toBeNull();
    expect(screen.queryByText("Copy prompt")).toBeNull();
    expect(screen.queryByText("Download")).toBeNull();
  });

  it("renders loading placeholder before image is ready, then shows download entry", () => {
    const { container } = renderWithLang(
      <ImageCardList
        images={[
          {
            imageId: "img-loading",
            storageKey: "generated-images/demo/img-loading.png",
            prompt: longPrompt,
            provider: "zhipu",
            model: "glm-image",
            width: 1280,
            height: 1280,
          },
        ]}
      />,
      { lang: "zh" }
    );

    expect(container.querySelector(".generated-image-card-loading")).not.toBeNull();
    expect(screen.queryByRole("link", { name: "下载图片" })).toBeNull();

    fireEvent.load(screen.getByAltText("生成图片"));
    expect(container.querySelector(".generated-image-card-loading")).toBeNull();
    expect(screen.getByRole("link", { name: "下载图片" })).toBeInTheDocument();
  });

  it("renders pending glass placeholder when image list is empty but pending exists", () => {
    renderWithLang(<ImageCardList images={[]} pendingCount={1} />, { lang: "zh" });

    expect(screen.getByTestId("generated-image-card-pending")).toBeInTheDocument();
    expect(screen.getByText("生成图片...")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "下载图片" })).toBeNull();
  });

  it("copies the full prompt when the preview text is clicked and then restores it", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(window.navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    renderWithLang(
      <ImageCardList
        images={[
          {
            imageId: "img-2",
            storageKey: "generated-images/demo/img-2.png",
            prompt: longPrompt,
            provider: "qwen",
            model: "qwen-image-2.0-pro",
            width: 1024,
            height: 1024,
          },
        ]}
      />,
      { lang: "zh" }
    );

    const promptButton = screen.getByRole("button", { name: "复制图片提示词" });
    const initialPreview = promptButton.textContent ?? "";

    await act(async () => {
      promptButton.click();
      await Promise.resolve();
    });

    expect(writeText).toHaveBeenCalledWith(longPrompt);
    expect(promptButton).toHaveTextContent("已复制");

    act(() => {
      vi.advanceTimersByTime(1600);
    });

    expect(promptButton.textContent).toBe(initialPreview);
  });

  it("localizes the download icon label in Chinese", () => {
    renderWithLang(
      <ImageCardList
        images={[
          {
            imageId: "img-3",
            storageKey: "generated-images/demo/img-3.png",
            prompt: "一只暖色调的小蜜蜂",
            provider: "zhipu",
            model: "glm-image",
            width: 1280,
            height: 1280,
          },
        ]}
      />,
      { lang: "zh" }
    );

    fireEvent.load(screen.getByAltText("生成图片"));
    expect(screen.getByRole("link", { name: "下载图片" })).toBeInTheDocument();
  });
});
