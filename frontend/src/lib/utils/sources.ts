import { RawSource } from "@/lib/api/types";

export type NormalizedSource = {
  document_id: string;
  chunk_id: string;
  title: string;
  text: string;
  score: number;
};

export function normalizeSource(source: RawSource): NormalizedSource {
  return {
    document_id: source.document_id || "",
    chunk_id: source.chunk_id || "",
    title: source.title || "",
    text: source.text ?? source.content ?? "",
    score: Number(source.score ?? 0),
  };
}

export function normalizeSources(sources: RawSource[] = []): NormalizedSource[] {
  return sources.map(normalizeSource);
}
