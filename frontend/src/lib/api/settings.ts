import { apiFetch } from "@/lib/api/client";

export type MCPServerStatus = {
  name: string;
  transport: string;
  enabled: boolean;
  connection_status: string;
  tool_count: number;
  error_message?: string | null;
};

export type MCPServersStatusResponse = {
  mcp_enabled: boolean;
  servers: MCPServerStatus[];
};

export type UpdateSettingResponse = {
  key: string;
  value: string;
};

export function getMCPServersStatus() {
  return apiFetch<MCPServersStatusResponse>("/settings/mcp/servers");
}

export function updateSetting(key: string, value: string) {
  return apiFetch<UpdateSettingResponse>("/settings", {
    method: "PUT",
    body: { key, value },
  });
}
