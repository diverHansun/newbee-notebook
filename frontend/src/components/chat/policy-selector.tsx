"use client";

import { useEffect, useRef, useState } from "react";

import type { EffectivePolicy, PolicyPreferenceUpdate } from "@/lib/api/types";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type PolicySelectorProps = {
  policy: EffectivePolicy;
  disabled?: boolean;
  disabledReason?: string;
  onChange: (update: PolicyPreferenceUpdate) => void;
};

function ShieldIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 1.8 13 3.7v3.8c0 3.1-2 5.7-5 6.7-3-1-5-3.6-5-6.7V3.7L8 1.8Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path
        d="M3 4.5 6 7.5 9 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function PolicySelector({
  policy,
  disabled = false,
  disabledReason,
  onChange,
}: PolicySelectorProps) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const isFullAccess = policy.policy === "yolo";
  const hasSession = Boolean(policy.session_id);
  const label = isFullAccess
    ? t(uiStrings.policyPermission.fullAccessPolicy)
    : t(uiStrings.policyPermission.defaultPolicy);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (target && rootRef.current?.contains(target)) return;
      setOpen(false);
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const chooseDefault = () => {
    if (!hasSession && policy.source !== "notebook") {
      setOpen(false);
      return;
    }
    onChange({
      scope: policy.source === "notebook" ? "notebook" : "session",
      session_id: policy.session_id,
      policy: "default",
    });
    setOpen(false);
  };

  const chooseFullAccess = () => {
    if (!hasSession) return;
    onChange({
      scope: "session",
      session_id: policy.session_id,
      policy: "yolo",
    });
    setOpen(false);
  };

  return (
    <div className="policy-selector" ref={rootRef}>
      <button
        type="button"
        className={`policy-selector-trigger${isFullAccess ? " is-yolo" : ""}`}
        aria-label={t(uiStrings.policyPermission.policyButtonLabel)}
        aria-expanded={open}
        disabled={disabled}
        title={disabledReason}
        onClick={() => {
          if (!disabled) setOpen((value) => !value);
        }}
      >
        <ShieldIcon />
        <span className="policy-selector-label">{label}</span>
        <span className="policy-selector-chevron" aria-hidden="true">
          <ChevronDownIcon />
        </span>
      </button>
      {open ? (
        <div className="policy-selector-menu" role="menu">
          <button
            type="button"
            role="menuitem"
            className="policy-selector-item"
            onClick={chooseDefault}
          >
            <span>{t(uiStrings.policyPermission.defaultPolicy)}</span>
            {!isFullAccess ? <span aria-hidden="true">✓</span> : null}
          </button>
          <button
            type="button"
            role="menuitem"
            className="policy-selector-item"
            onClick={chooseFullAccess}
            disabled={!hasSession}
          >
            <span>{t(uiStrings.policyPermission.fullAccessPolicy)}</span>
            {isFullAccess ? <span aria-hidden="true">✓</span> : null}
          </button>
        </div>
      ) : null}
    </div>
  );
}
