import { Badge } from '@mantine/core';
import { ArrowUpRight } from 'lucide-react';
import type { LinkFinding } from '../lib/types';

const STATUS: Record<LinkFinding['status'], { label: string; color: string }> = {
  read: { label: 'Read', color: 'teal' },
  not_read: { label: 'Not opened', color: 'gray' },
  failed: { label: 'Could not be read', color: 'orange' },
};

function safeUrl(value: string) {
  return /^https?:\/\//i.test(value) ? value : null;
}

function formatDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function LinkFindings({ links }: { links: LinkFinding[] }) {
  return (
    <section className="link-findings" aria-labelledby="links-heading">
      <div className="section-heading">
        <h2 id="links-heading">Links</h2>
        <span>
          {links.length} {links.length === 1 ? 'link' : 'links'}
        </span>
      </div>
      {links.map((link) => {
        const url = safeUrl(link.url);
        const status = STATUS[link.status];
        return (
          <article className="link-card" key={link.url}>
            <div className="link-title">
              {url ? (
                <a href={url} target="_blank" rel="noopener noreferrer" dir="auto">
                  {link.title || link.site || link.url} <ArrowUpRight size={13} aria-hidden />
                </a>
              ) : (
                <span>{link.url}</span>
              )}
              <Badge variant="light" color={status.color} tt="none">
                {status.label}
              </Badge>
            </div>
            <p className="muted small">
              {[
                link.site,
                link.published_on
                  ? `Published ${formatDate(link.published_on)} (reported by a search index)`
                  : link.status === 'read'
                    ? 'Publication date unknown'
                    : null,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
            {link.status === 'read' && (
              <p className="small">
                Page text was read
                {link.truncated ? ' (first part only)' : ''} and checked like pasted text
                {link.media_ids.length
                  ? '; its main image is shown under Images and video.'
                  : '.'}{' '}
                The page itself is not used as evidence for its own claims.
              </p>
            )}
            {link.reason && <p className="muted small">{link.reason}</p>}
          </article>
        );
      })}
    </section>
  );
}
