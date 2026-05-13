/**
 * Short-lived map keyed by placeholderId -> raw chart fence content.
 * Populated by markdown-pipeline at compile time, consumed by MarkdownViewer
 * when replacing placeholder divs with InlineChartCard components.
 */

const registry = new Map<string, string>();

let counter = 0;

function generatePlaceholderId(): string {
  counter += 1;
  return `ec-${counter.toString(36)}-${Date.now().toString(36)}`;
}

export function registerInlineChartPayload(rawContent: string): string {
  const id = generatePlaceholderId();
  registry.set(id, rawContent);
  return id;
}

export function getInlineChartPayload(placeholderId: string): string | null {
  return registry.get(placeholderId) ?? null;
}

export function disposeInlineChartPayload(placeholderId: string): void {
  registry.delete(placeholderId);
}

export const INLINE_CHART_PLACEHOLDER_ATTR = "data-chart-placeholder";
export const INLINE_CHART_PAYLOAD_ID_ATTR = "data-payload-id";
export const INLINE_CHART_TYPE_ATTR = "data-chart-type";

/** Test-only helper. */
export function _resetInlineChartRegistryForTests(): void {
  registry.clear();
  counter = 0;
}
