/** Recorded investigation events and how the web app and extension describe them. */
export const BASE_STAGES = [
  {
    event: 'graph_started',
    title: 'Receive input',
    detail: 'Save the original passage in your workspace.',
  },
  {
    event: 'extract_claims',
    title: 'Separate claims',
    detail: 'Identify individual statements, keeping the original wording.',
  },
  {
    event: 'evaluate_evidence',
    title: 'Check evidence',
    detail: 'Assess the available evidence and identify unresolved details.',
  },
  {
    event: 'validate_report',
    title: 'Validate report',
    detail: 'Check claim references and the evidence structure.',
  },
  {
    event: 'report_saved',
    title: 'Save results',
    detail: 'Keep the report and model usage for later inspection.',
  },
];

export const RESEARCH_STAGES = [
  { event: 'plan_queries', title: 'Plan searches', detail: 'Map research questions to claims.' },
  {
    event: 'retrieve_sources',
    title: 'Find sources',
    detail: 'Search and read sources within the available budget.',
  },
  {
    event: 'select_passages',
    title: 'Select passages',
    detail: 'Find relevant passages in the collected sources.',
  },
  {
    event: 'assess_components',
    title: 'Assess details',
    detail: 'Compare each detail with its source evidence.',
  },
];

export const MEDIA_STAGE = {
  event: 'analyze_media',
  title: 'Read images and video',
  detail: 'Read visible text, transcribe speech and search where the pictures appeared.',
};

export const LINK_STAGE = {
  event: 'fetch_links',
  title: 'Read links',
  detail: 'Open linked pages and take their text and main image.',
};

export const FOLLOWUP_STAGE = {
  event: 'followup_research',
  title: 'Search again',
  detail: 'Look once more for details the first sources left unsettled.',
};

const ALL_STAGES = [...BASE_STAGES, ...RESEARCH_STAGES, MEDIA_STAGE, LINK_STAGE, FOLLOWUP_STAGE];

/** What a queued investigation waits for; null once it runs. */
export function queueMessage(status: string, position: number | null | undefined) {
  if (status !== 'queued') return null;
  if (!position) return 'Starting next: another investigation is finishing.';
  return `Waiting for ${position} earlier ${position === 1 ? 'investigation' : 'investigations'} to finish.`;
}

/** The title for a recorded event, or null for events without one. */
export function stageTitle(event: string): string | null {
  return ALL_STAGES.find((stage) => stage.event === event)?.title ?? null;
}
