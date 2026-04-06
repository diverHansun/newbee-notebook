"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Session } from "@/lib/api/types";
import {
  buildSessionDisplayTitleMap,
  getSessionDisplayTitle,
} from "@/lib/chat/session-labels";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type SessionSelectProps = {
  sessions: Session[];
  currentSessionId: string | null;
  onChange: (sessionId: string) => void;
};

function ChevronDownIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M4 6.5L8 10L12 6.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SessionSelect({ sessions, currentSessionId, onChange }: SessionSelectProps) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const placeholder = t(uiStrings.chat.sessionSelect);
  const sessionTitleMap = useMemo(
    () => buildSessionDisplayTitleMap(sessions, t(uiStrings.chat.defaultSessionTitle)),
    [sessions, t]
  );

  const currentSession = useMemo(
    () => sessions.find((item) => item.session_id === currentSessionId) || null,
    [currentSessionId, sessions]
  );
  const currentSessionLabel = getSessionDisplayTitle(currentSession, sessionTitleMap, placeholder);

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target || rootRef.current?.contains(target)) return;
      setOpen(false);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };

    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="session-select" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={`session-select-trigger${open ? " is-open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={currentSessionLabel}
        disabled={sessions.length === 0}
        onClick={() => {
          if (sessions.length === 0) return;
          setOpen((prev) => !prev);
        }}
      >
        <span className={`session-select-trigger-label${currentSession ? "" : " is-placeholder"}`}>
          {currentSessionLabel}
        </span>
        <span className="session-select-trigger-icon">
          <ChevronDownIcon />
        </span>
      </button>

      {open && (
        <div
          className="session-select-menu"
          role="listbox"
          aria-label={placeholder}
          style={{ maxHeight: "320px", overflowY: "auto" }}
        >
          {sessions.map((session) => {
            const selected = session.session_id === currentSessionId;
            const label = getSessionDisplayTitle(session, sessionTitleMap, placeholder);

            return (
              <button
                key={session.session_id}
                type="button"
                role="option"
                aria-selected={selected}
                className={`session-select-option${selected ? " is-selected" : ""}`}
                title={label}
                onClick={() => {
                  setOpen(false);
                  onChange(session.session_id);
                }}
              >
                <span className="session-select-option-label">{label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
