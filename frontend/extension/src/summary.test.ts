import type { Report } from '../../src/lib/types';
import { summarize } from './summary';

const report = {
  investigation_id: 'r1',
  mode: 'meta',
  revision: 1,
  claims: Array.from({ length: 7 }, (_, i) => ({ id: `c${i}`, text: `Claim ${i}` })),
  sources: [],
  evidence: [],
  findings: Array.from({ length: 7 }, (_, i) => ({
    id: `f${i}`,
    claim_id: `c${i}`,
    assessment: 'unresolved',
    explanation: '',
    evidence_ids: [],
    components:
      i === 0
        ? [
            { status: 'insufficient' },
            { status: 'supported' },
            { status: 'insufficient' },
            { status: 'contradicted' },
          ]
        : [],
  })),
  limitations: [],
  model_usage: [],
  media: [
    {
      kind: 'video',
      analysis: {
        caption_checks: [
          { caption_detail: 'Izmir', assessment: 'inconsistent', visible_basis: [] },
          { caption_detail: 'roofs', assessment: 'consistent', visible_basis: [] },
        ],
      },
      origin: {
        matches: [
          { match: 'similar', published_on: '2010-01-01', date_text: 'Jan 1, 2010', source: 'X' },
          { match: 'full', published_on: null, date_text: 'Oct 15, 2013', source: 'Facebook' },
          { match: 'full', published_on: '2018-09-15', date_text: 'Sep 15, 2018', source: 'YTN' },
        ],
      },
    },
  ],
  links: [{ status: 'failed' }, { status: 'read' }],
  research_summary: { budget_limited_claim_ids: ['c5', 'c6'] },
} as unknown as Report;

it('summarizes claims, the picture and what was left out', () => {
  const summary = summarize(report);
  expect(summary.claims).toHaveLength(5);
  expect(summary.hiddenClaims).toBe(2);
  // Settled details first.
  expect(summary.claims[0].counts).toEqual([
    ['contradicted', 1],
    ['supported', 1],
    ['insufficient', 2],
  ]);
  // A similar picture or a social page date is not the earliest publication.
  expect(summary.media).toEqual([
    { kind: 'video', earliest: 'Sep 15, 2018, YTN', mismatches: ['Izmir'] },
  ]);
  expect([summary.unreadableLinks, summary.budgetLimited]).toEqual([1, 2]);
});
