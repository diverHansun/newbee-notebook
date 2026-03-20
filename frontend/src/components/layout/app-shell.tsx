"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { Panel, Group, Separator } from "react-resizable-panels";

import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

type AppShellProps = {
  title: string;
  left: ReactNode;
  main: ReactNode;
  right: ReactNode;
  mainOverlay?: ReactNode;
};

export function AppShell({ title, left, main, right, mainOverlay }: AppShellProps) {
  const { t } = useLang();

  return (
    <div className="page-shell">
      {/* Header */}
      <header className="page-header">
        <div className="row">
          <Link
            href="/notebooks"
            className="text-sm font-semibold tracking-tight"
            style={{
              color: "inherit",
              borderBottom: "2px solid hsl(var(--bee-yellow))",
              paddingBottom: 1,
            }}
          >
            Newbee Notebook
          </Link>
          <span className="muted">/</span>
          <span className="text-sm font-medium">{title}</span>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <Link href="/notebooks" className="btn btn-ghost btn-sm">
            {t(uiStrings.layout.backToList)}
          </Link>
        </div>
      </header>

      {/* Three-column resizable workspace */}
      <main style={{ flex: 1, overflow: "hidden" }}>
        <Group
          orientation="horizontal"
          id="notebook-panels"
          style={{ height: "100%" }}
        >
          {/* Sources Panel — 25% default, min 15% */}
          <Panel id="sources" defaultSize="25%" minSize="200px" maxSize="40%">
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
          <Panel id="studio" defaultSize="25%" minSize="160px" maxSize="40%">
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
