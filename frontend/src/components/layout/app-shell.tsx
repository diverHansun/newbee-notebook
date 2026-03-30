"use client";

import { ReactNode } from "react";
import { Panel, Group, Separator } from "react-resizable-panels";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type AppShellProps = {
  left: ReactNode;
  main: ReactNode;
  right: ReactNode;
  mainOverlay?: ReactNode;
};

export function AppShell({ left, main, right, mainOverlay }: AppShellProps) {
  const { t } = useLang();

  return (
    <div className="page-shell">
      {/* Three-column resizable workspace */}
      <main style={{ flex: 1, overflow: "hidden" }}>
        <Group
          orientation="horizontal"
          id="notebook-panels"
          style={{ height: "100%" }}
        >
          {/* Sources Panel — 25% default, min 15% */}
          <Panel id="sources" defaultSize="25%" minSize="200px" maxSize="35%">
            <section
              className="panel"
              style={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                borderRadius: 0,
                borderTop: "none",
                background: "hsl(var(--accent))",
              }}
            >
              <div className="panel-head">
                <span>{t(uiStrings.layout.sourcesPanel)}</span>
              </div>
              <div className="panel-body" style={{ flex: 1, overflow: "auto" }}>
                {left}
              </div>
            </section>
          </Panel>

          <Separator id="sep-sources-main" className="resize-handle" />

          {/* Main Panel — 50% default, min 30% */}
          <Panel id="main" defaultSize="50%" minSize="320px" style={{ overflow: "visible" }}>
            <section
              id="main-panel-section"
              className="panel"
              style={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                borderRadius: 0,
                borderTop: "none",
                position: "relative",
                overflow: "visible",
              }}
            >
              <div className="panel-head">
                <span>{t(uiStrings.layout.mainPanel)}</span>
              </div>
              <div className="panel-body" style={{ flex: 1, overflow: "hidden", padding: 0 }}>
                {main}
              </div>
              {mainOverlay}
            </section>
          </Panel>

          <Separator id="sep-main-studio" className="resize-handle" />

          {/* Studio Panel — 25% default, min 15% */}
          <Panel id="studio" defaultSize="25%" minSize="160px" maxSize="55%">
            <section
              className="panel studio-panel"
              style={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                borderRadius: 0,
                borderTop: "none",
                background: "hsl(var(--accent))",
              }}
            >
              <div className="panel-head">
                <span>{t(uiStrings.layout.studioPanel)}</span>
              </div>
              <div className="panel-body" style={{ flex: 1, overflow: "auto" }}>
                {right}
              </div>
            </section>
          </Panel>
        </Group>
      </main>
    </div>
  );
}
