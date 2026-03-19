import { ReactElement, ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";

import { LanguageContext, type Lang } from "@/lib/i18n/language-context";

type RenderWithLangOptions = RenderOptions & {
  lang?: Lang;
};

export function renderWithLang(
  ui: ReactElement,
  { lang = "en", ...options }: RenderWithLangOptions = {}
) {
  return render(
    <LanguageContext.Provider value={{ lang, setLang: () => {} }}>{ui}</LanguageContext.Provider>,
    options
  );
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function createHookWrapper(lang: Lang = "en") {
  const queryClient = createQueryClient();

  return function HookWrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <LanguageContext.Provider value={{ lang, setLang: () => {} }}>
          {children}
        </LanguageContext.Provider>
      </QueryClientProvider>
    );
  };
}
