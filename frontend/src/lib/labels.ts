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
