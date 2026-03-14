"use client";

import { useQuery } from "@tanstack/react-query";

import { MCPConfigPanel } from "@/components/layout/mcp-config-panel";
import { ModelConfigPanel } from "@/components/layout/model-config-panel";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { getHealthStatus, getSystemInfo } from "@/lib/api/system";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";
import { useTheme } from "@/lib/theme/theme-context";

export type ControlPanelTab = "language" | "theme" | "model" | "mcp" | "about";

type ControlPanelNavIconName =
  | ControlPanelTab
  | "rag"
  | "mcp"
  | "skills";

type ControlPanelProps = {
  panelId: string;
  activeTab: ControlPanelTab;
  onSelectTab: (tab: ControlPanelTab) => void;
};

type ActiveNavItem = {
  key: Exclude<ControlPanelTab, "about">;
};

type DisabledNavItem = {
  key: "rag" | "skills";
};

const ACTIVE_ITEMS: ActiveNavItem[] = [
  { key: "language" },
  { key: "theme" },
  { key: "model" },
  { key: "mcp" },
];

const DISABLED_ITEMS: DisabledNavItem[] = [
  { key: "rag" },
  { key: "skills" },
];

function ControlPanelNavIcon({ name }: { name: ControlPanelNavIconName }) {
  switch (name) {
    case "language":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M4 8h10" />
          <path d="M9 4v4c0 5-2 8-5 10" />
          <path d="M7 12c1 2 3 4 5 5" />
          <path d="M14 6h6" />
          <path d="M17 6v12" />
          <path d="M14 14h6" />
        </svg>
      );
    case "theme":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
        </svg>
      );
    case "model":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <rect x="4" y="4" width="7" height="7" rx="1.5" />
          <rect x="13" y="4" width="7" height="7" rx="1.5" />
          <rect x="4" y="13" width="7" height="7" rx="1.5" />
          <rect x="13" y="13" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "rag":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <ellipse cx="10" cy="7" rx="5" ry="2.5" />
          <path d="M5 7v7c0 1.4 2.2 2.5 5 2.5 1.1 0 2.1-.2 3-.5" />
          <path d="M5 10c0 1.4 2.2 2.5 5 2.5" />
          <circle cx="17.5" cy="16.5" r="2.5" />
          <path d="M19.4 18.4 21 20" />
        </svg>
      );
    case "mcp":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M8 8h4a4 4 0 1 1 0 8H8" />
          <path d="M8 6v12" />
          <path d="M4 9v6" />
          <path d="M16 10v4" />
          <path d="M20 11v2" />
        </svg>
      );
    case "skills":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <path d="M12 3l1.2 3.3L16.5 7.5l-3.3 1.2L12 12l-1.2-3.3L7.5 7.5l3.3-1.2L12 3Z" />
          <path d="M18 13l.8 2.2L21 16l-2.2.8L18 19l-.8-2.2L15 16l2.2-.8L18 13Z" />
          <path d="M7 14l.8 2.2L10 17l-2.2.8L7 20l-.8-2.2L4 17l2.2-.8L7 14Z" />
        </svg>
      );
    case "about":
      return (
        <svg viewBox="0 0 24 24" aria-hidden>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 10v6" />
          <path d="M12 7h.01" />
        </svg>
      );
    default:
      return null;
  }
}

export function ControlPanel({ panelId, activeTab, onSelectTab }: ControlPanelProps) {
  const { lang, setLang, t } = useLang();
  const { theme, setTheme } = useTheme();

  const aboutVisible = activeTab === "about";

  const infoQuery = useQuery({
    queryKey: ["system-info"],
    queryFn: getSystemInfo,
    enabled: aboutVisible,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });

  const healthQuery = useQuery({
    queryKey: ["system-health"],
    queryFn: getHealthStatus,
    enabled: aboutVisible,
    staleTime: 30_000,
    refetchInterval: aboutVisible ? 30_000 : false,
    retry: false,
  });

  const backendConnected = !healthQuery.isError && healthQuery.data?.status === "ok";

  return (
    <div
      id={panelId}
      className="control-panel-popover"
      role="dialog"
      aria-label={t(uiStrings.controlPanel.title)}
      aria-modal="false"
    >
      <div className="control-panel-shell">
        <aside className="control-panel-nav" aria-label={t(uiStrings.controlPanel.title)}>
          <div className="control-panel-nav-group">
            {ACTIVE_ITEMS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`control-panel-nav-item${activeTab === item.key ? " is-active" : ""}`}
                onClick={() => onSelectTab(item.key)}
              >
                <span className="control-panel-nav-icon" aria-hidden>
                  <ControlPanelNavIcon name={item.key} />
                </span>
                <span>{t(uiStrings.controlPanel[item.key])}</span>
              </button>
            ))}

            {DISABLED_ITEMS.map((item) => (
              <div key={item.key} className="control-panel-nav-item is-disabled" aria-disabled="true">
                <span className="control-panel-nav-icon" aria-hidden>
                  <ControlPanelNavIcon name={item.key} />
                </span>
                <span className="control-panel-nav-label">{t(uiStrings.controlPanel[item.key])}</span>
                <span className="control-panel-badge">{t(uiStrings.controlPanel.comingSoon)}</span>
              </div>
            ))}
          </div>

          <div className="control-panel-nav-footer">
            <button
              type="button"
              className={`control-panel-nav-item${activeTab === "about" ? " is-active" : ""}`}
              onClick={() => onSelectTab("about")}
            >
              <span className="control-panel-nav-icon" aria-hidden>
                <ControlPanelNavIcon name="about" />
              </span>
              <span>{t(uiStrings.controlPanel.about)}</span>
            </button>
          </div>
        </aside>

        <section className="control-panel-content">
          {activeTab === "language" && (
            <div className="control-panel-card">
              <div className="control-panel-card-title">{t(uiStrings.controlPanel.interfaceLanguage)}</div>
              <div className="control-panel-card-hint">{t(uiStrings.controlPanel.langSwitchHint)}</div>
              <div className="control-panel-card-body">
                <SegmentedControl
                  value={lang}
                  options={[
                    { value: "zh", label: "中文" },
                    { value: "en", label: "EN" },
                  ]}
                  onChange={(next) => setLang(next as "zh" | "en")}
                />
              </div>
            </div>
          )}

          {activeTab === "theme" && (
            <div className="control-panel-card">
              <div className="control-panel-card-title">{t(uiStrings.controlPanel.colorScheme)}</div>
              <div className="control-panel-card-hint">{t(uiStrings.controlPanel.themeSwitchHint)}</div>
              <div className="control-panel-card-body">
                <SegmentedControl
                  value={theme}
                  options={[
                    { value: "light", label: t(uiStrings.controlPanel.themeLight) },
                    { value: "dark", label: t(uiStrings.controlPanel.themeDark) },
                  ]}
                  onChange={(next) => setTheme(next as "light" | "dark")}
                />
              </div>
            </div>
          )}

          {activeTab === "model" && <ModelConfigPanel />}

          {activeTab === "mcp" && <MCPConfigPanel />}

          {activeTab === "about" && (
            <div className="control-panel-stack">
              <div className="control-panel-card">
                <div className="control-panel-card-title">{t(uiStrings.controlPanel.appInfo)}</div>
                <div className="control-panel-card-body control-panel-rows">
                  <div className="control-panel-row">
                    <span className="muted">{t(uiStrings.controlPanel.appName)}</span>
                    <span>{infoQuery.data?.name ?? "Newbee Notebook"}</span>
                  </div>
                  <div className="control-panel-row">
                    <span className="muted">{t(uiStrings.controlPanel.version)}</span>
                    <span>
                      {infoQuery.isLoading
                        ? t(uiStrings.common.loading)
                        : infoQuery.data?.version || "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="control-panel-card">
                <div className="control-panel-card-title">{t(uiStrings.controlPanel.connectionStatus)}</div>
                <div className="control-panel-card-body control-panel-rows">
                  <div className="control-panel-row">
                    <span className="muted">{t(uiStrings.controlPanel.backend)}</span>
                    <span className="control-panel-status">
                      <span
                        className={`control-panel-status-dot${backendConnected ? " is-ok" : " is-error"}`}
                        aria-hidden
                      />
                      {healthQuery.isLoading
                        ? t(uiStrings.controlPanel.checking)
                        : backendConnected
                          ? t(uiStrings.controlPanel.connected)
                          : t(uiStrings.controlPanel.disconnected)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
