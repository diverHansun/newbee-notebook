"use client";

import { usePathname } from "next/navigation";
import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";

import { ControlPanel, type ControlPanelTab } from "@/components/layout/control-panel";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

export function ControlPanelIcon() {
  const { t } = useLang();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<ControlPanelTab>("language");
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;

    const onMouseDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const isDev = process.env.NODE_ENV !== "production";

  return (
    <div ref={rootRef} className={`control-panel-root${isDev ? " is-dev" : ""}`}>
      <button
        type="button"
        className="control-panel-button"
        aria-label={open ? t(uiStrings.controlPanel.closeSettings) : t(uiStrings.controlPanel.openSettings)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="control-panel-button-mark" aria-hidden>
          <Image src="/assets/images/newbee-icon.jpg" alt="Newbee Notebook" width={60} height={60} unoptimized priority />
        </span>
      </button>

      {open ? (
        <ControlPanel panelId={panelId} activeTab={activeTab} onSelectTab={setActiveTab} />
      ) : null}
    </div>
  );
}

