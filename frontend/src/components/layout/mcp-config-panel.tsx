"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  getMCPServersStatus,
  updateSetting,
  type MCPServerStatus,
} from "@/lib/api/settings";
import { useLang } from "@/lib/hooks/useLang";
import { uiStrings } from "@/lib/i18n/strings";

function formatConnectionStatus(
  status: MCPServerStatus["connection_status"],
  t: ReturnType<typeof useLang>["t"]
) {
  switch (status) {
    case "connected":
      return t(uiStrings.controlPanel.connected);
    case "connecting":
      return t(uiStrings.controlPanel.mcpStatusConnecting);
    case "disabled":
      return t(uiStrings.controlPanel.mcpStatusDisabled);
    case "error":
      return t(uiStrings.controlPanel.mcpStatusError);
    default:
      return status;
  }
}

function serverSettingKey(serverName: string) {
  return `mcp.servers.${serverName}.enabled`;
}

export function MCPConfigPanel() {
  const { t } = useLang();
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ["mcp-servers-status"],
    queryFn: getMCPServersStatus,
    staleTime: 15_000,
    retry: false,
  });

  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      updateSetting(key, value),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["mcp-servers-status"] });
    },
  });

  const errorMessage =
    updateMutation.error instanceof Error
      ? updateMutation.error.message
      : statusQuery.error instanceof Error
        ? statusQuery.error.message
        : null;

  if (statusQuery.isLoading) {
    return (
      <div className="control-panel-card">
        <div className="control-panel-card-title">
          {t(uiStrings.controlPanel.mcp)}
        </div>
        <div className="control-panel-card-hint">{t(uiStrings.common.loading)}</div>
      </div>
    );
  }

  const mcpEnabled = statusQuery.data?.mcp_enabled ?? false;
  const servers = statusQuery.data?.servers ?? [];

  return (
    <div className="control-panel-stack">
      {errorMessage ? (
        <div className="control-panel-error">
          {t(uiStrings.controlPanel.configSaveFailed)}: {errorMessage}
        </div>
      ) : null}

      <div className="control-panel-card">
        <div className="control-panel-card-title">
          {t(uiStrings.controlPanel.mcpGlobal)}
        </div>
        <div className="control-panel-card-hint">
          {t(uiStrings.controlPanel.mcpGlobalHint)}
        </div>
        <div className="control-panel-card-body control-panel-stack">
          <SegmentedControl
            value={mcpEnabled ? "enabled" : "disabled"}
            options={[
              { value: "enabled", label: t(uiStrings.controlPanel.connected) },
              { value: "disabled", label: t(uiStrings.controlPanel.disconnected) },
            ]}
            disabled={updateMutation.isPending}
            onChange={(next) => {
              const enabled = next === "enabled";
              updateMutation.mutate({
                key: "mcp.enabled",
                value: enabled ? "true" : "false",
              });
            }}
          />

          <div className="control-panel-readonly-row">
            <span className="control-panel-readonly-label">
              {t(uiStrings.controlPanel.mcpConfigPath)}
            </span>
            <span>configs/mcp.json</span>
          </div>

          <button
            type="button"
            className="control-panel-reset-btn control-panel-inline-btn"
            onClick={() => void statusQuery.refetch()}
            disabled={statusQuery.isFetching}
          >
            {t(uiStrings.common.refresh)}
          </button>
        </div>
      </div>

      <div className="control-panel-card">
        <div className="control-panel-card-title">
          {t(uiStrings.controlPanel.mcpServers)}
        </div>
        <div className="control-panel-card-hint">
          {t(uiStrings.controlPanel.mcpServersHint)}
        </div>
        <div className="control-panel-card-body">
          {servers.length === 0 ? (
            <div className="control-panel-warning">
              {t(uiStrings.controlPanel.mcpEmpty)}
            </div>
          ) : (
            <div className="control-panel-mcp-list">
              {servers.map((server) => {
                const serverEnabled = mcpEnabled && server.enabled;
                return (
                  <div key={server.name} className="control-panel-mcp-item">
                    <div className="control-panel-mcp-item-header">
                      <div>
                        <div className="control-panel-mcp-item-title">
                          {server.name}
                        </div>
                        <div className="control-panel-mcp-item-meta">
                          {server.transport}
                        </div>
                      </div>
                      <SegmentedControl
                        value={serverEnabled ? "enabled" : "disabled"}
                        options={[
                          {
                            value: "enabled",
                            label: t(uiStrings.controlPanel.connected),
                          },
                          {
                            value: "disabled",
                            label: t(uiStrings.controlPanel.disconnected),
                          },
                        ]}
                        disabled={updateMutation.isPending || !mcpEnabled}
                        onChange={(next) => {
                          const enabled = next === "enabled";
                          updateMutation.mutate({
                            key: serverSettingKey(server.name),
                            value: enabled ? "true" : "false",
                          });
                        }}
                      />
                    </div>

                    <div className="control-panel-mcp-rows">
                      <div className="control-panel-readonly-row">
                        <span className="control-panel-readonly-label">
                          {t(uiStrings.controlPanel.connectionStatus)}
                        </span>
                        <span className="control-panel-status">
                          <span
                            className={`control-panel-status-dot${
                              server.connection_status === "connected"
                                ? " is-ok"
                                : server.connection_status === "error"
                                  ? " is-error"
                                  : ""
                            }`}
                            aria-hidden
                          />
                          {formatConnectionStatus(server.connection_status, t)}
                        </span>
                      </div>
                      <div className="control-panel-readonly-row">
                        <span className="control-panel-readonly-label">
                          {t(uiStrings.controlPanel.mcpToolCount)}
                        </span>
                        <span>{server.tool_count}</span>
                      </div>
                    </div>

                    {server.error_message ? (
                      <div className="control-panel-warning">
                        {server.error_message}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
