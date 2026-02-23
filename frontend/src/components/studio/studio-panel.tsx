"use client";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

export function StudioPanel() {
  const { t } = useLang();
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: 24,
        textAlign: "center",
      }}
    >
      <p className="muted" style={{ fontSize: 13 }}>
        {t(uiStrings.studio.comingSoon)}
      </p>
    </div>
  );
}
