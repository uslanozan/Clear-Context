import type { ResearchMode } from './types';

// Budgets mirror RESEARCH_MODES in services/investigation_research.py.
export const RESEARCH_MODES: {
  value: Exclude<ResearchMode, 'complete'>;
  label: string;
  detail: string;
}[] = [
  {
    value: 'fast',
    label: 'Fast',
    detail: 'Up to 3 searches; every page found is read. No second search for unsettled details.',
  },
  {
    value: 'balanced',
    label: 'Balanced',
    detail:
      'Up to 6 searches; every page found is read, plus one more search for details left unsettled.',
  },
  {
    value: 'deep',
    label: 'Deep',
    detail:
      'Up to 10 searches; every page found is read, plus a wider second search. Uses more credits and may reach search rate limits.',
  },
];

export function modeLabel(mode: ResearchMode) {
  return mode === 'complete'
    ? 'Every claim'
    : (RESEARCH_MODES.find((item) => item.value === mode)?.label ?? mode);
}

// Mirrors COMPLETE_MAX_CLAIMS, COMPLETE_BATCH_CLAIMS and batch_budget() in
// services/investigation_research.py.
export const COMPLETE_MAX_CLAIMS = 40;
const COMPLETE_BATCH_CLAIMS = 8;

/** Upper bounds for researching `claims` claims in complete mode. */
export function completeEstimate(claims: number) {
  const researched = Math.min(claims, COMPLETE_MAX_CLAIMS);
  let searches = 0;
  let modelCalls = 0;
  for (let start = 0; start < researched; start += COMPLETE_BATCH_CLAIMS) {
    const batch = Math.min(COMPLETE_BATCH_CLAIMS, researched - start);
    const queries = Math.min(2 * batch + 2, 40);
    const followup = Math.max(2, Math.floor(batch / 2));
    searches += queries + followup;
    // Planning, passage selection for every page read, and judgments, with the follow-up.
    modelCalls += 2 + 3 * queries + 3 * batch + 3 * followup + followup;
  }
  return { researched, left: claims - researched, searches, modelCalls };
}
