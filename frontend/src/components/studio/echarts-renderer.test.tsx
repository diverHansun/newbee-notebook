import { render, screen, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { initMock, setOptionMock, disposeMock, resizeMock, getDataURLMock, ensureRegisteredMock } =
  vi.hoisted(() => ({
    initMock: vi.fn(),
    setOptionMock: vi.fn(),
    disposeMock: vi.fn(),
    resizeMock: vi.fn(),
    getDataURLMock: vi.fn(() => "data:image/png;base64,FAKE"),
    ensureRegisteredMock: vi.fn(),
  }));

vi.mock("@/lib/diagram/echarts-modules", () => ({
  ensureEChartsRegistered: ensureRegisteredMock,
  ECHARTS_SERIES_TYPE_WHITELIST: ["bar", "line", "pie"],
  echarts: {
    init: initMock,
  },
}));

vi.mock("file-saver", () => ({
  saveAs: vi.fn(),
}));

let themeOverride: "light" | "dark" = "light";
vi.mock("@/lib/theme/theme-context", () => ({
  useTheme: () => ({ theme: themeOverride, setTheme: vi.fn() }),
}));

import { EChartsRenderer } from "@/components/studio/echarts-renderer";

function buildInstance() {
  return {
    setOption: setOptionMock,
    dispose: disposeMock,
    resize: resizeMock,
    getDataURL: getDataURLMock,
  };
}

describe("EChartsRenderer", () => {
  beforeEach(() => {
    initMock.mockReset();
    setOptionMock.mockReset();
    disposeMock.mockReset();
    resizeMock.mockReset();
    getDataURLMock.mockReset().mockReturnValue("data:image/png;base64,FAKE");
    ensureRegisteredMock.mockReset();
    initMock.mockImplementation(() => buildInstance());
    themeOverride = "light";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("initializes echarts and calls setOption with parsed content", () => {
    render(
      <EChartsRenderer
        content='{"series":[{"type":"bar","data":[1,2,3]}]}'
      />
    );

    expect(ensureRegisteredMock).toHaveBeenCalledTimes(1);
    expect(initMock).toHaveBeenCalledTimes(1);
    expect(setOptionMock).toHaveBeenCalledTimes(1);
    const [option] = setOptionMock.mock.calls[0];
    expect(option.series[0].type).toBe("bar");
    expect(option.backgroundColor).toBe("transparent");
  });

  it("re-inits with dark theme when isDark and applies textStyle overlay", () => {
    themeOverride = "dark";
    render(
      <EChartsRenderer
        content='{"series":[{"type":"line","data":[1]}]}'
      />
    );

    expect(initMock).toHaveBeenCalledTimes(1);
    expect(initMock.mock.calls[0][1]).toBe("dark");
    const [option] = setOptionMock.mock.calls[0];
    expect(option.textStyle.color).toBeDefined();
  });

  it("falls back to <pre> when JSON parse fails", () => {
    render(<EChartsRenderer content={"{ not json"} />);

    expect(initMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("echarts-renderer-fallback")).toBeInTheDocument();
  });

  it("falls back to <pre> when content is empty", () => {
    render(<EChartsRenderer content={"   "} />);

    expect(initMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("echarts-renderer-fallback")).toBeInTheDocument();
  });

  it("calls dispose on unmount", () => {
    const { unmount } = render(
      <EChartsRenderer
        content='{"series":[{"type":"pie","data":[]}]}'
      />
    );

    expect(disposeMock).not.toHaveBeenCalled();
    unmount();
    expect(disposeMock).toHaveBeenCalledTimes(1);
  });

  it("exposes exportImage via ref calling getDataURL and saveAs", async () => {
    const fileSaver = await import("file-saver");
    const ref = { current: null as null | { exportImage: (n: string) => Promise<void> } };

    vi.stubGlobal("fetch", vi.fn(async () => new Response(new Blob(["png-bytes"]))));

    render(
      <EChartsRenderer
        ref={ref}
        content='{"series":[{"type":"bar","data":[1]}]}'
      />
    );

    await act(async () => {
      await ref.current!.exportImage("chart.png");
    });

    expect(getDataURLMock).toHaveBeenCalledTimes(1);
    expect(fileSaver.saveAs).toHaveBeenCalledTimes(1);
  });
});
