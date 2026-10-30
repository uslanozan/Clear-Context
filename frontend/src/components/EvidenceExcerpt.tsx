import type { Report } from '../lib/types';
import { ArrowUpRight } from 'lucide-react';

type EvidenceItem = Report['evidence'][number];
type SourceItem = Report['sources'][number];

export function EvidenceExcerpt({
  evidence,
  source,
}: {
  evidence: EvidenceItem;
  source?: SourceItem;
}) {
  const start = source?.content.indexOf(evidence.excerpt) ?? -1;
  const unique = start >= 0 && source?.content.indexOf(evidence.excerpt, start + 1) === -1;
  const before = unique && source ? source.content.slice(Math.max(0, start - 180), start) : '';
  const after =
    unique && source
      ? source.content.slice(start + evidence.excerpt.length, start + evidence.excerpt.length + 180)
      : '';
  let url: URL | null = null;
  try {
    const candidate = new URL(source?.url ?? '');
    if (['http:', 'https:'].includes(candidate.protocol)) url = candidate;
  } catch {
    // Some older reports contain no usable source URL.
  }

  return (
    <div className="evidence-excerpt">
      <blockquote dir="auto">
        {unique ? (
          <>
            {before}
            {before && ' '}
            <mark>{evidence.excerpt}</mark>
            {after && ' '}
            {after}
          </>
        ) : (
          evidence.excerpt
        )}
      </blockquote>
      {url && (
        <a href={url.href} target="_blank" rel="noopener noreferrer">
          {source?.title || url.hostname} <ArrowUpRight size={13} aria-hidden="true" />
        </a>
      )}
      {!unique && <p className="muted">Source context could not be located uniquely.</p>}
    </div>
  );
}
