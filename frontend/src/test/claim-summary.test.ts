import { claimSummary, type ComponentStatus } from '../lib/labels';

const details = (...statuses: ComponentStatus[]) =>
  statuses.map((status) => ({
    description: 'A detail',
    status,
    explanation: 'Recorded.',
    evidence_ids: [],
    evidence_relations: {},
    context_evidence_ids: [],
  }));

it.each([
  [['supported'], 'Supported'],
  [['insufficient'], 'Insufficient evidence'],
  [['supported', 'supported'], 'All details supported'],
  [['supported', 'supported', 'insufficient'], 'Mostly supported'],
  [['supported', 'insufficient', 'insufficient', 'not_assessed'], 'Partly supported'],
  [['supported', 'insufficient'], 'Partly supported'],
  [['supported', 'contradicted', 'insufficient'], 'Mixed results'],
  [['contradicted', 'contradicted'], 'All details contradicted'],
  [['contradicted', 'contradicted', 'conflicting'], 'Mostly contradicted'],
  [['contradicted', 'insufficient', 'insufficient'], 'Partly contradicted'],
  [['conflicting', 'insufficient'], 'Sources disagree'],
  [['insufficient', 'not_assessed'], 'Not settled'],
  [['not_assessed', 'not_assessed'], 'Not assessed'],
] as [ComponentStatus[], string][])('%j is summarized as %s', (statuses, label) => {
  expect(claimSummary(details(...statuses))?.label).toBe(label);
});

it('has no summary without details', () => {
  expect(claimSummary([])).toBeNull();
});
