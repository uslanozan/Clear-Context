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
export type ResearchMode = 'fast' | 'balanced' | 'deep';
export interface CaptionCheck {
  caption_detail: string;
  assessment: 'consistent' | 'inconsistent' | 'cannot_tell';
  visible_basis: string[];
}
export interface PriorFactCheck {
  url: string;
  title: string | null;
  publisher: string | null;
  site: string | null;
  rating: string | null;
  review_date: string | null;
  claim_text: string | null;
}
export interface MediaFinding {
  id: string;
  kind: 'image' | 'video';
  mime_type: string;
  filename: string;
  analysis: {
    status: 'analyzed' | 'not_analyzed' | 'failed';
    content_type: string | null;
    visible_text: string;
    // Older reports predate statement selection and caption checks.
    claim_text?: string[];
    observations: string[];
    context_cues: string[];
    caption_checks?: CaptionCheck[];
    note: string | null;
  };
  // Absent in reports saved before fact check search.
  prior_checks?: {
    status: 'not_checked' | 'found' | 'none' | 'failed';
    provider: string | null;
    reason: string | null;
    reviews: PriorFactCheck[];
  };
  origin: {
    status: 'not_checked' | 'matches_found' | 'no_matches' | 'failed';
    provider: string | null;
    reason: string | null;
    matches: {
      page_url: string;
      page_title: string | null;
      image_url: string | null;
      match: 'full' | 'partial' | 'similar';
      source?: string | null;
      date_text?: string | null;
      published_on?: string | null;
    }[];
    best_guess_labels: string[];
  };
}
export interface Investigation {
  id: string;
  text: string;
  status: Status;
  mode: 'mock' | 'meta';
  research_mode?: ResearchMode;
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
      status: 'supported' | 'contradicted' | 'conflicting' | 'insufficient' | 'not_assessed';
      explanation: string;
      evidence_ids: string[];
      evidence_relations: Record<string, 'supports' | 'contradicts'>;
      context_evidence_ids: string[];
    }[];
  }[];
  limitations: string[];
  model_usage: ModelUsage[];
  analyzed_text?: string | null;
  media?: MediaFinding[];
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
