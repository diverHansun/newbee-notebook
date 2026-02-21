export type PaginationInfo = {
  total: number;
  limit: number;
  offset: number;
  has_next: boolean;
  has_prev: boolean;
};

export type ApiListResponse<T> = {
  data: T[];
  pagination: PaginationInfo;
};

export type Notebook = {
  notebook_id: string;
  title: string;
  description: string | null;
  session_count: number;
  document_count: number;
  created_at: string;
  updated_at: string;
};

export type LibraryInfo = {
  library_id: string;
  document_count: number;
  created_at: string;
  updated_at: string;
};

export type DocumentStatus =
  | "uploaded"
  | "pending"
  | "processing"
  | "converted"
  | "completed"
  | "failed";

export type ProcessingStage =
  | "queued"
  | "converting"
  | "splitting"
  | "indexing_pg"
  | "indexing_es"
  | "finalizing";

export type DocumentItem = {
  document_id: string;
  title: string;
  content_type: string;
  status: DocumentStatus;
  library_id?: string | null;
  notebook_id?: string | null;
  page_count: number;
  chunk_count: number;
  file_size: number;
  content_path?: string | null;
  content_format?: string | null;
  content_size?: number | null;
  error_message?: string | null;
  processing_stage?: ProcessingStage | null;
  stage_updated_at?: string | null;
  processing_meta?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type NotebookDocumentItem = {
  document_id: string;
  title: string;
  status: DocumentStatus;
  content_type: string;
  file_size: number;
  page_count: number;
  chunk_count: number;
  processing_stage?: ProcessingStage | null;
  stage_updated_at?: string | null;
  processing_meta?: Record<string, unknown> | null;
  created_at: string;
  added_at?: string | null;
};

export type UploadFailure = {
  filename: string;
  reason: string;
};

export type UploadDocumentsResponse = {
  documents: DocumentItem[];
  total: number;
  failed: UploadFailure[];
};

export type NotebookDocumentsAddItem = {
  document_id: string;
  title: string;
  status: DocumentStatus;
  action: "none" | "index_only" | "full_pipeline";
  processing_stage?: ProcessingStage | null;
};

export type NotebookDocumentsProblemItem = {
  document_id: string;
  reason: string;
};

export type NotebookDocumentsAddResponse = {
  notebook_id: string;
  added: NotebookDocumentsAddItem[];
  skipped: NotebookDocumentsProblemItem[];
  failed: NotebookDocumentsProblemItem[];
};

export type DocumentContentResponse = {
  document_id: string;
  title: string;
  format: "markdown" | "text";
  content: string;
  page_count: number;
  content_size: number;
};

export type Session = {
  session_id: string;
  notebook_id: string;
  title: string | null;
  message_count: number;
  include_ec_context: boolean;
  created_at: string;
  updated_at: string;
};

export type MessageRole = "user" | "assistant" | "system";
export type MessageMode = "chat" | "ask" | "explain" | "conclude";

export type SessionMessage = {
  message_id: number;
  session_id: string;
  mode: MessageMode;
  role: MessageRole;
  content: string;
  created_at: string;
};

export type ChatContext = {
  selected_text?: string;
  chunk_id?: string;
  document_id?: string;
  page_number?: number;
};

export type RawSource = {
  document_id?: string;
  chunk_id?: string;
  title?: string;
  text?: string;
  content?: string;
  score?: number;
};

export type ChatResponse = {
  session_id: string;
  message_id: number;
  content: string;
  mode: MessageMode;
  sources: RawSource[];
};

export type ChatRequest = {
  message: string;
  mode: MessageMode;
  session_id?: string;
  context?: ChatContext | null;
  include_ec_context?: boolean | null;
};

export type SseEventStart = {
  type: "start";
  message_id: number;
};

export type SseEventContent = {
  type: "content";
  delta: string;
};

export type SseEventSources = {
  type: "sources";
  sources: RawSource[];
};

export type SseEventDone = {
  type: "done";
};

export type SseEventError = {
  type: "error";
  error_code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type SseEventHeartbeat = {
  type: "heartbeat";
};

export type SseEvent =
  | SseEventStart
  | SseEventContent
  | SseEventSources
  | SseEventDone
  | SseEventError
  | SseEventHeartbeat;

export type ApiErrorPayload = {
  error_code?: string;
  message?: string;
  detail?: unknown;
  details?: Record<string, unknown>;
};
