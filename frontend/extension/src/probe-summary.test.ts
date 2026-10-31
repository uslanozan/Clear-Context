import type { Report } from '../../src/lib/types';
import { probePage } from './page-probe';
import { summarize } from './summary';

afterEach(() => {
  document.body.innerHTML = '';
  window.getSelection()?.removeAllRanges();
});

function feed() {
  // The shape of a post on X: an article whose timestamp links to the post.
  document.body.innerHTML = `
    <main>
      <article>
        <a href="/obsrvate"><span>Obsrvate</span></a>
        <a href="/obsrvate/status/2116292001104794001"><time>19h</time></a>
        <div id="text">Drake's girlfriend posted a video</div>
        <img id="photo" src="https://pbs.example/media/1.jpg">
      </article>
      <p id="outside">Trending now</p>
    </main>`;
}

function select(id: string) {
  const range = document.createRange();
  range.selectNodeContents(document.getElementById(id)!.firstChild!);
  window.getSelection()!.addRange(range);
}

it('finds the post link around a selection or a picture on a feed', () => {
  feed();
  select('text');
  expect(probePage(null).post).toBe('http://localhost:3000/obsrvate/status/2116292001104794001');
  expect(probePage('https://pbs.example/media/1.jpg').post).toBe(
    'http://localhost:3000/obsrvate/status/2116292001104794001',
  );
});

it('returns no post outside one, and no rectangle for a missing picture', () => {
  feed();
  select('outside');
  expect(probePage(null).post).toBeNull();
  expect(probePage('https://pbs.example/other.jpg')).toEqual({
    rect: null,
    viewportWidth: window.innerWidth,
    post: null,
  });
});

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
