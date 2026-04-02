import type { Metadata } from "next";
import { Sora } from "next/font/google";
import { ReactNode } from "react";

import { ControlPanelIcon } from "@/components/layout/control-panel-icon";
import { AppProvider } from "@/components/providers/app-provider";

import "./globals.css";

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: "Newbee Notebook",
  description: "Frontend P1 architecture scaffold",
  icons: {
    icon: "/assets/images/newbee-icon.jpg",
    shortcut: "/assets/images/newbee-icon.jpg",
    apple: "/assets/images/newbee-icon.jpg",
  },
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="zh-CN" suppressHydrationWarning className={sora.variable}>
      <body className="min-h-screen font-sans antialiased">
        <AppProvider>
          {children}
          <ControlPanelIcon />
        </AppProvider>
      </body>
    </html>
  );
}
