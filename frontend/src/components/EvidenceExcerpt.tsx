import type { Report } from '../lib/types';
import { ArrowUpRight } from 'lucide-react';

type EvidenceItem = Report['evidence'][number];
type SourceItem = Report['sources'][number];

const CONTEXT_CHARS = 180;

/**
 * Trims surrounding source text to whole words and drops table-like page chrome
 * (for example calendar widgets joined by pipes). The excerpt itself is never changed.
 */
function trimContext(raw: string, side: 'before' | 'after'): string {
  const pipe = side === 'before' ? raw.lastIndexOf('|') : raw.indexOf('|');
  if (pipe >= 0) {
    return (side === 'before' ? raw.slice(pipe + 1) : raw.slice(0, pipe)).trim();
  }
  // A full-length slice may end mid-word; shorter ones reached the document edge.
  if (raw.length < CONTEXT_CHARS) return raw.trim();
  return (side === 'before' ? raw.replace(/^\S*\s/, '') : raw.replace(/\s\S*$/, '')).trim();
}

const SOURCE_TYPES: Record<string, string> = {
  fact_check: 'Fact check',
  reference: 'Reference',
  social: 'Social post or forum',
};

/** Label for the kind of site; other web pages get none. Not a reliability rating. */
export function SourceTypeLabel({ type }: { type?: string | null }) {
  const label = type ? SOURCE_TYPES[type] : undefined;
  return label ? <span className={`source-type source-type-${type}`}>{label}</span> : null;
}

/** Readable source name: its title, or the domain when the title is missing or just a URL. */
export function sourceDisplayName(source: { title?: string; url: string } | undefined): string {
  const title = source?.title?.trim();
  if (title && !/^https?:\/\//i.test(title)) return title;
  try {
    return new URL(title || source?.url || '').hostname.replace(/^www\./, '');
  } catch {
    return title || source?.url || 'Source';
  }
}

export function EvidenceExcerpt({
  evidence,
  source,
  showSource = true,
}: {
  evidence: EvidenceItem;
  source?: SourceItem;
  /** Set to false when a neighbouring excerpt from the same source already names it. */
  showSource?: boolean;
}) {
  const start = source?.content.indexOf(evidence.excerpt) ?? -1;
  const unique = start >= 0 && source?.content.indexOf(evidence.excerpt, start + 1) === -1;
  const rawBefore =
    unique && source ? source.content.slice(Math.max(0, start - CONTEXT_CHARS), start) : '';
  const rawAfter =
    unique && source
      ? source.content.slice(
          start + evidence.excerpt.length,
          start + evidence.excerpt.length + CONTEXT_CHARS,
        )
      : '';
  const before = trimContext(rawBefore, 'before');
  const after = trimContext(rawAfter, 'after');
  const hasMoreBefore = unique && start > 0 && before !== '';
  const hasMoreAfter =
    unique && !!source && start + evidence.excerpt.length < source.content.length;
  let url: URL | null = null;
  try {
    const candidate = new URL(source?.url ?? '');
    if (['http:', 'https:'].includes(candidate.protocol)) url = candidate;
  } catch {
    // Some older reports contain no usable source URL.
  }

  return (
    <div className="evidence-excerpt">
      {url && showSource && (
        <a className="evidence-source" href={url.href} target="_blank" rel="noopener noreferrer">
          {sourceDisplayName(source)} <ArrowUpRight size={13} aria-hidden="true" />
        </a>
      )}
      {url && showSource && <SourceTypeLabel type={source?.source_type} />}
      <blockquote dir="auto">
        {unique ? (
          <>
            {hasMoreBefore && '… '}
            {before}
            {before && ' '}
            <mark>{evidence.excerpt}</mark>
            {after && ' '}
            {after}
            {hasMoreAfter && after && ' …'}
          </>
        ) : (
          evidence.excerpt
        )}
      </blockquote>
      {!unique && <p className="muted">Source context could not be located uniquely.</p>}
    </div>
  );
}
