import { apiFetch } from "@/lib/api/client";

export type SystemInfoResponse = {
  name: string;
  version: string;
  features?: Record<string, unknown>;
};

export type HealthStatusResponse = {
  status: string;
};

export function getSystemInfo() {
  return apiFetch<SystemInfoResponse>("/info");
}

export function getHealthStatus() {
  return apiFetch<HealthStatusResponse>("/health");
}

