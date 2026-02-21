import type { Metadata } from "next";
import { ReactNode } from "react";

import { AppProvider } from "@/components/providers/app-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "Newbee Notebook",
  description: "Frontend P1 architecture scaffold",
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="min-h-screen font-sans antialiased">
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
