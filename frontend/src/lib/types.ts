export type Status = 'queued' | 'running' | 'completed' | 'failed';
export type Assessment = 'supported' | 'contradicted' | 'mixed' | 'unresolved';
export interface ModelUsage {
  task: string;
  model_id: string;
  prompt_version?: string | null;
  prompt_sha256?: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cached_input_tokens: number | null;
  chunk_start?: number | null;
  chunk_end?: number | null;
  outcome?: 'accepted' | 'capacity_reached' | 'truncated' | 'invalid' | null;
}
export interface TextSpan {
  start: number;
  end: number;
  text: string;
}
export interface ExtractedClaim {
  group?: string | null;
  id: string;
  text: string;
  statement?: string | null;
  source_span?: TextSpan | null;
  context_spans?: TextSpan[];
  context_status?: 'standalone' | 'context_linked' | 'ambiguous' | null;
}
export interface Investigation {
  id: string;
  text: string;
  status: Status;
  mode: 'mock' | 'meta';
  revision: number;
  created_at: string;
  updated_at: string;
  error_code: string | null;
  model_usage: ModelUsage[];
}
export interface ResearchStep {
  name: string;
  status: Status;
  created_at: string;
}
export interface Report {
  investigation_id: string;
  mode: 'mock' | 'meta';
  revision: number;
  claims: ExtractedClaim[];
  sources: { id: string; url: string; title: string; content: string }[];
  evidence: { id: string; claim_id: string; source_id: string; excerpt: string }[];
  findings: {
    id: string;
    claim_id: string;
    assessment: Assessment;
    explanation: string;
    evidence_ids: string[];
    components?: {
      description: string;
      status: 'supported' | 'contradicted' | 'conflicting' | 'insufficient';
      explanation: string;
      evidence_ids: string[];
      evidence_relations: Record<string, 'supports' | 'contradicts'>;
      context_evidence_ids: string[];
    }[];
  }[];
  limitations: string[];
  model_usage: ModelUsage[];
  extraction_coverage?: {
    status: 'processed' | 'partial';
    model_calls: number;
    chunks: {
      start: number;
      end: number;
      status: 'processed' | 'split' | 'partial';
      reason: string | null;
    }[];
    notes?: string[];
  } | null;
}
export interface Health {
  status: string;
  mode: 'mock' | 'meta';
  paid_api_calls_enabled: boolean;
  research_enabled?: boolean;
}
