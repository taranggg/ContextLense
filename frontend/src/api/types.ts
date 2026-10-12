// Mirrors backend/app/schemas.py

export type DocumentStatus =
  | "queued"
  | "extracting"
  | "chunking"
  | "embedding"
  | "indexing"
  | "ready"
  | "failed";

export interface DocumentInfo {
  id: string;
  filename: string;
  status: DocumentStatus;
  is_sample: boolean;
  size_bytes: number;
  page_count: number | null;
  pages_with_text: number | null;
  chunk_count: number | null;
  word_count: number | null;
  embedding_model: string | null;
  chunk_size_words: number | null;
  chunk_overlap_words: number | null;
  error_code: string | null;
  error_message: string | null;
  warnings: string[];
  created_at: string;
  updated_at: string;
}

export interface UploadError {
  filename: string;
  code: string;
  message: string;
}

export interface BatchUploadResult {
  documents: DocumentInfo[];
  errors: UploadError[];
}

export interface Chunk {
  chunk_id: string;
  document_id: string;
  document_name: string;
  index: number;
  pages: number[];
  text: string;
  word_count: number;
}

export interface ChunkPage {
  document_id: string;
  total: number;
  offset: number;
  limit: number;
  chunks: Chunk[];
}

export interface RetrievedChunk {
  rank: number;
  source_label: string;
  chunk_id: string;
  document_id: string;
  document_name: string;
  pages: number[];
  text: string;
  word_count: number;
  similarity: number;
}

export interface Citation {
  source_label: string;
  rank: number;
  chunk_id: string;
  document_id: string;
  document_name: string;
  pages: number[];
  excerpt_pages: number[];
  similarity: number;
  excerpt: string;
}

export interface Latency {
  retrieval_ms: number;
  generation_ms: number | null;
  total_ms: number;
}

export interface ModelInfo {
  runtime: string;
  model: string;
  temperature: number;
  top_p: number;
  max_tokens: number;
  context_tokens: number;
}

export interface GenerationStats {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  finish_reason: string | null;
  context_truncated: boolean;
  sources_in_prompt: number;
}

export interface ChatResponse {
  question: string;
  answer: string;
  abstained: boolean;
  citations: Citation[];
  invalid_citations: string[];
  retrieved: RetrievedChunk[];
  k: number;
  latency: Latency;
  model: ModelInfo;
  generation: GenerationStats;
  cancelled: boolean;
}

export type ComponentState =
  | "ready"
  | "loading"
  | "not_loaded"
  | "unavailable"
  | "not_downloaded"
  | "not_configured"
  | "error";

export interface ComponentStatus {
  status: ComponentState;
  detail: string | null;
}

export interface Readiness {
  ready: boolean;
  backend: ComponentStatus;
  storage: ComponentStatus;
  embedding: ComponentStatus;
  llm: ComponentStatus & { runtime: string; model: string; load_time_s: number | null };
  documents_ready: number;
  limits: {
    max_upload_mb: number;
    max_files_per_upload: number;
    default_top_k: number;
    research_k_values: number[];
    max_question_chars: number;
  };
}

export interface ClaimCheck {
  claim: string;
  label: "supported" | "unsupported";
  support_ratio: number;
  missing_numbers: string[];
}

export interface ConditionMetrics {
  abstained: boolean;
  citation_count: number;
  invalid_citation_count: number;
  citation_validity: number | null;
  claims_total: number;
  claims_lexically_supported: number;
  claims_lexically_unsupported: number;
  claim_checks: ClaimCheck[];
  method: string;
}

export interface ConditionResult {
  condition: string;
  k: number | null;
  answer: string | null;
  citations: Citation[];
  invalid_citations: string[];
  retrieved: RetrievedChunk[];
  latency: Latency | null;
  generation: GenerationStats | null;
  metrics: ConditionMetrics | null;
  error: string | null;
}

export interface ExperimentSettings {
  model: ModelInfo;
  embedding_model: string;
  similarity: string;
  chunk_size_words: number;
  chunk_overlap_words: number;
  prompt_version: string;
}

export interface Comparison {
  id: string;
  created_at: string;
  question: string;
  document_ids: string[];
  document_names: string[];
  settings: ExperimentSettings;
  conditions: ConditionResult[];
  evaluation_status: string;
}

export interface ComparisonSummary {
  id: string;
  created_at: string;
  question: string;
  document_names: string[];
  conditions: string[];
}

export interface ConditionAggregate {
  n: number;
  errors: number;
  accuracy_normalised_mean: number | null;
  accuracy_score_counts: Record<string, number>;
  abstention_rate: number | null;
  context_fact_recall_mean: number | null;
  context_fact_bearing_precision_mean: number | null;
  gold_page_retrieved_rate: number | null;
  claims_total: number;
  claims_lexically_supported_rate: number | null;
  citation_validity_mean: number | null;
  cites_gold_page_rate: number | null;
  retrieval_ms_median: number | null;
  generation_ms_median: number | null;
  total_ms_median: number | null;
  total_ms_mean: number | null;
  prompt_tokens_mean: number | null;
  context_truncated_count: number;
}

export interface PairedTest {
  metric: string;
  a: string;
  b: string;
  n: number;
  mean_a: number | null;
  mean_b: number | null;
  mean_diff_b_minus_a: number | null;
  p_value: number | null;
  p_holm: number | null;
  note: string | null;
}

export interface BenchmarkSummary {
  run_id: string;
  status: "complete" | "partial";
  started_at: string;
  finished_at: string;
  question_count: number;
  completed_runs: number;
  planned_runs: number;
  conditions: string[];
  benchmark_note: string;
  documents: { id: string; filename: string }[];
  model: ModelInfo;
  embedding_model: string;
  chunk_size_words: number;
  chunk_overlap_words: number;
  prompt_version: string;
  validation_counts: Record<string, number>;
  validated_question_count: number;
  evaluation: Record<string, string>;
  by_condition: Record<string, ConditionAggregate>;
  by_condition_validated_subset: Record<string, ConditionAggregate>;
  paired_tests: PairedTest[];
}

export interface ResearchResults {
  comparisons: ComparisonSummary[];
  benchmark_runs: BenchmarkSummary[];
}

export interface ApiErrorBody {
  error?: { code: string; message: string };
}
