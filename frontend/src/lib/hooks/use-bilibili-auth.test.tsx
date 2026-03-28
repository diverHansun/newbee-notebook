import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageContext } from "@/lib/i18n/language-context";
import { createQueryClient } from "@/test/test-utils";

const apiMocks = vi.hoisted(() => ({
  getBilibiliAuthStatus: vi.fn(),
  logoutBilibili: vi.fn(),
}));

vi.mock("@/lib/api/bilibili-auth", () => ({
  getBilibiliAuthStatus: (...args: unknown[]) => apiMocks.getBilibiliAuthStatus(...args),
  logoutBilibili: (...args: unknown[]) => apiMocks.logoutBilibili(...args),
}));

import {
  BILIBILI_AUTH_STATUS_QUERY_KEY,
  useBilibiliAuthStatus,
  useBilibiliLogout,
} from "@/lib/hooks/use-bilibili-auth";

function createWrapper() {
  const queryClient = createQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <LanguageContext.Provider value={{ lang: "en", setLang: () => {} }}>
        {children}
      </LanguageContext.Provider>
    </QueryClientProvider>
  );
  return { queryClient, wrapper };
}

describe("use-bilibili-auth", () => {
  beforeEach(() => {
    apiMocks.getBilibiliAuthStatus.mockReset();
    apiMocks.logoutBilibili.mockReset();
  });

  it("loads bilibili login status", async () => {
    apiMocks.getBilibiliAuthStatus.mockResolvedValue({ logged_in: true });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useBilibiliAuthStatus(), { wrapper });

    await waitFor(() => {
      expect(result.current.data?.logged_in).toBe(true);
    });
  });

  it("refreshes auth status after logout", async () => {
    apiMocks.getBilibiliAuthStatus.mockResolvedValue({ logged_in: true });
    apiMocks.logoutBilibili.mockResolvedValue(undefined);

    const { queryClient, wrapper } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useBilibiliLogout(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(apiMocks.logoutBilibili).toHaveBeenCalledOnce();
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: BILIBILI_AUTH_STATUS_QUERY_KEY });
  });
});
