import {
  CircleCheck,
  CircleDashed,
  CircleMinus,
  CircleX,
  Scale,
  type LucideIcon,
} from 'lucide-react';
import { claimSummary, COMPONENT_STATUS, type ComponentStatus } from '../lib/labels';
import type { Assessment, Report } from '../lib/types';

type Tone = 'supported' | 'contradicted' | 'conflicting' | 'open' | 'muted';

const TONE_ICON: Record<Tone, LucideIcon> = {
  supported: CircleCheck,
  contradicted: CircleX,
  conflicting: Scale,
  open: CircleDashed,
  muted: CircleMinus,
};

const COMPONENT_TONE: Record<ComponentStatus, Tone> = {
  supported: 'supported',
  contradicted: 'contradicted',
  conflicting: 'conflicting',
  insufficient: 'open',
  not_assessed: 'muted',
};

export const ASSESSMENT_LABEL: Record<Assessment, string> = {
  supported: 'Supported',
  contradicted: 'Contradicted',
  mixed: 'Mixed evidence',
  unresolved: 'Unresolved',
};

const ASSESSMENT_TONE: Record<Assessment, Tone> = {
  supported: 'supported',
  contradicted: 'contradicted',
  mixed: 'conflicting',
  unresolved: 'open',
};

function Tag({ tone, label, size }: { tone: Tone; label: string; size: 'sm' | 'lg' }) {
  const Icon = TONE_ICON[tone];
  return (
    <span className={`verdict-tag verdict-${tone} verdict-${size}`}>
      <Icon size={size === 'lg' ? 16 : 13} strokeWidth={2} aria-hidden="true" />
      {label}
    </span>
  );
}

/** A tag in the color and icon of a detail result, with its own label. */
export function VerdictLabel({ tone, label }: { tone: ComponentStatus; label: string }) {
  return <Tag tone={COMPONENT_TONE[tone]} label={label} size="sm" />;
}

/** The result for one detail of a claim. */
export function DetailTag({
  status,
  size = 'sm',
}: {
  status: ComponentStatus;
  size?: 'sm' | 'lg';
}) {
  return <Tag tone={COMPONENT_TONE[status]} label={COMPONENT_STATUS[status].label} size={size} />;
}

/**
 * The claim-wide result. With per-detail results it is counted from those results
 * (see claimSummary); older reports without details show their saved assessment.
 */
export function ClaimVerdict({
  assessment,
  components = [],
  size = 'lg',
}: {
  assessment: Assessment;
  components?: NonNullable<Report['findings'][number]['components']>;
  size?: 'sm' | 'lg';
}) {
  const summary = claimSummary(components);
  if (summary) return <Tag tone={COMPONENT_TONE[summary.tone]} label={summary.label} size={size} />;
  return (
    <Tag tone={ASSESSMENT_TONE[assessment]} label={ASSESSMENT_LABEL[assessment]} size={size} />
  );
}
