"use client";

import { ReactNode } from "react";

import { QueryProvider } from "@/components/providers/query-provider";
import { LanguageProvider } from "@/lib/i18n/language-context";

type AppProviderProps = {
  children: ReactNode;
};

export function AppProvider({ children }: AppProviderProps) {
  return (
    <LanguageProvider>
      <QueryProvider>{children}</QueryProvider>
    </LanguageProvider>
  );
}
