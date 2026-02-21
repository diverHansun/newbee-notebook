"use client";

import { ReactNode } from "react";

import { QueryProvider } from "@/components/providers/query-provider";

type AppProviderProps = {
  children: ReactNode;
};

export function AppProvider({ children }: AppProviderProps) {
  return <QueryProvider>{children}</QueryProvider>;
}
