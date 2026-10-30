import type { ResearchMode } from './types';

// Budgets mirror RESEARCH_MODES in services/investigation_research.py.
export const RESEARCH_MODES: { value: ResearchMode; label: string; detail: string }[] = [
  {
    value: 'fast',
    label: 'Fast',
    detail: 'Up to 3 searches and 2 sources. No second search for unsettled details.',
  },
  {
    value: 'balanced',
    label: 'Balanced',
    detail: 'Up to 6 searches and 3 sources, plus one more search for details left unsettled.',
  },
  {
    value: 'deep',
    label: 'Deep',
    detail:
      'Up to 10 searches and 5 sources, plus a wider second search. Uses more credits and may reach search rate limits.',
  },
];
