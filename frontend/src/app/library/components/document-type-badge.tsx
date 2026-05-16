"use client";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type DocumentTypeBadgeProps = {
  contentType: string;
};

export function DocumentTypeBadge({ contentType }: DocumentTypeBadgeProps) {
  const { ti } = useLang();
  const label = (contentType || "").toUpperCase() || "—";
  const aria = ti(uiStrings.libraryPage.typeBadgeAriaLabel, { type: label });

  return (
    <span className="badge badge-default" aria-label={aria} title={aria}>
      {label}
    </span>
  );
}
