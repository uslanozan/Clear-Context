import type { Report } from './types';

export type ComponentStatus = NonNullable<
  Report['findings'][number]['components']
>[number]['status'];

/** How a detail's assessment is shown in the report and the extension summary. */
export const COMPONENT_STATUS: Record<ComponentStatus, { label: string; color: string }> = {
  supported: { label: 'Supported', color: 'teal' },
  contradicted: { label: 'Contradicted', color: 'red' },
  conflicting: { label: 'Sources disagree', color: 'orange' },
  insufficient: { label: 'Insufficient evidence', color: 'yellow' },
  not_assessed: { label: 'Not assessed', color: 'gray' },
};

/** Order for summaries: what was settled first, then what was not. */
export const STATUS_ORDER: ComponentStatus[] = [
  'contradicted',
  'conflicting',
  'supported',
  'insufficient',
  'not_assessed',
];

/** Counts of detail results, settled outcomes first, e.g. "1 supported · 2 insufficient evidence". */
export function detailSummary(
  components: NonNullable<Report['findings'][number]['components']>,
): string {
  return STATUS_ORDER.map((status) => {
    const count = components.filter((component) => component.status === status).length;
    return count ? `${count} ${COMPONENT_STATUS[status].label.toLowerCase()}` : null;
  })
    .filter(Boolean)
    .join(' · ');
}

export type ClaimSummaryKey =
  | 'all_supported'
  | 'mostly_supported'
  | 'partly_supported'
  | 'mixed'
  | 'partly_contradicted'
  | 'mostly_contradicted'
  | 'all_contradicted'
  | 'disagree'
  | 'unsettled'
  | 'not_assessed';

/** Claim-wide summary labels, counted from detail results; no model decides them. */
export const CLAIM_SUMMARY: Record<
  ClaimSummaryKey,
  { label: string; tone: ComponentStatus; rule: string }
> = {
  all_supported: {
    label: 'All details supported',
    tone: 'supported',
    rule: 'Every detail is supported.',
  },
  mostly_supported: {
    label: 'Mostly supported',
    tone: 'supported',
    rule: 'More than half of the details are supported and none is contradicted.',
  },
  partly_supported: {
    label: 'Partly supported',
    tone: 'supported',
    rule: 'Some details are supported, none is contradicted, the rest are not settled.',
  },
  mixed: {
    label: 'Mixed results',
    tone: 'conflicting',
    rule: 'Some details are supported and others are contradicted.',
  },
  partly_contradicted: {
    label: 'Partly contradicted',
    tone: 'contradicted',
    rule: 'Some details are contradicted, none is supported, the rest are not settled.',
  },
  mostly_contradicted: {
    label: 'Mostly contradicted',
    tone: 'contradicted',
    rule: 'More than half of the details are contradicted and none is supported.',
  },
  all_contradicted: {
    label: 'All details contradicted',
    tone: 'contradicted',
    rule: 'Every detail is contradicted.',
  },
  disagree: {
    label: 'Sources disagree',
    tone: 'conflicting',
    rule: 'No detail is settled either way, and sources disagree on at least one.',
  },
  unsettled: {
    label: 'Not settled',
    tone: 'insufficient',
    rule: 'The details were checked, but the sources read settle none of them.',
  },
  not_assessed: {
    label: 'Not assessed',
    tone: 'not_assessed',
    rule: 'No detail was judged.',
  },
};

type Components = NonNullable<Report['findings'][number]['components']>;

/**
 * The claim-wide label from detail results alone. A claim with one detail takes that
 * detail's own result. Returns null when there are no details.
 */
export function claimSummary(
  components: Components,
): { label: string; tone: ComponentStatus; key: ClaimSummaryKey | ComponentStatus } | null {
  const total = components.length;
  if (!total) return null;
  if (total === 1) {
    const status = components[0].status;
    return { key: status, label: COMPONENT_STATUS[status].label, tone: status };
  }
  const count = (status: ComponentStatus) =>
    components.filter((component) => component.status === status).length;
  const supported = count('supported');
  const contradicted = count('contradicted');
  let key: ClaimSummaryKey;
  if (supported && contradicted) key = 'mixed';
  else if (contradicted)
    key =
      contradicted === total
        ? 'all_contradicted'
        : contradicted * 2 > total
          ? 'mostly_contradicted'
          : 'partly_contradicted';
  else if (supported)
    key =
      supported === total
        ? 'all_supported'
        : supported * 2 > total
          ? 'mostly_supported'
          : 'partly_supported';
  else if (count('conflicting')) key = 'disagree';
  else if (count('insufficient')) key = 'unsettled';
  else key = 'not_assessed';
  return { key, label: CLAIM_SUMMARY[key].label, tone: CLAIM_SUMMARY[key].tone };
}
