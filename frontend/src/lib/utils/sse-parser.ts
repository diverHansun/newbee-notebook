import { SseEvent } from "@/lib/api/types";

type SseParserOptions = {
  onEvent: (event: SseEvent) => void;
  signal?: AbortSignal;
};

function extractEventPayload(block: string): string | null {
  const lines = block.split("\n");
  const dataLines: string[] = [];
  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  return dataLines.join("\n");
}

function extractEventName(block: string): string | null {
  const lines = block.split("\n");
  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (line.startsWith("event:")) {
      return line.slice(6).trim();
    }
  }
  return null;
}

export async function parseSseStream(
  stream: ReadableStream<Uint8Array>,
  options: SseParserOptions
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      if (options.signal?.aborted) return;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");

      let separatorIndex = buffer.indexOf("\n\n");
      while (separatorIndex !== -1) {
        const chunk = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + 2);
        separatorIndex = buffer.indexOf("\n\n");

        const payload = extractEventPayload(chunk);
        if (!payload) continue;
        const parsed = JSON.parse(payload) as SseEvent;
        options.onEvent(parsed);
      }
    }

    const trailingPayload = extractEventPayload(buffer);
    if (trailingPayload) {
      options.onEvent(JSON.parse(trailingPayload) as SseEvent);
    }
  } finally {
    reader.releaseLock();
  }
}

type NamedSseParserOptions<TEvent> = {
  onEvent: (event: TEvent) => void;
  mapEvent: (eventName: string, payload: Record<string, unknown>) => TEvent | null;
  signal?: AbortSignal;
};

export async function parseNamedSseStream<TEvent>(
  stream: ReadableStream<Uint8Array>,
  options: NamedSseParserOptions<TEvent>
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      if (options.signal?.aborted) return;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");

      let separatorIndex = buffer.indexOf("\n\n");
      while (separatorIndex !== -1) {
        const chunk = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + 2);
        separatorIndex = buffer.indexOf("\n\n");

        const payload = extractEventPayload(chunk);
        const eventName = extractEventName(chunk);
        if (!payload || !eventName) continue;

        const mapped = options.mapEvent(eventName, JSON.parse(payload) as Record<string, unknown>);
        if (mapped !== null) {
          options.onEvent(mapped);
        }
      }
    }

    const trailingPayload = extractEventPayload(buffer);
    const trailingEventName = extractEventName(buffer);
    if (trailingPayload && trailingEventName) {
      const mapped = options.mapEvent(
        trailingEventName,
        JSON.parse(trailingPayload) as Record<string, unknown>
      );
      if (mapped !== null) {
        options.onEvent(mapped);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
