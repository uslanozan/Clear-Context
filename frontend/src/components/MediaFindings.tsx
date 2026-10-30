import { Badge } from '@mantine/core';
import { ArrowUpRight } from 'lucide-react';
import type { CaptionCheck, MediaFinding, PriorFactCheck } from '../lib/types';

const ANALYSIS: Record<MediaFinding['analysis']['status'], { label: string; color: string }> = {
  analyzed: { label: 'Read by model', color: 'teal' },
  not_analyzed: { label: 'Not analyzed', color: 'gray' },
  failed: { label: 'Analysis failed', color: 'red' },
};

function safeUrl(value: string | null) {
  return value && /^https?:\/\//i.test(value) ? value : null;
}

function plainTitle(title: string | null, url: string) {
  // Providers can return titles with markup; show text only.
  const text = (title ?? '').replace(/<[^>]*>/g, '').trim();
  return text || new URL(url).hostname.replace(/^www\./, '');
}

const CHECK: Record<CaptionCheck['assessment'], { label: string; color: string }> = {
  inconsistent: { label: 'Does not fit the image', color: 'orange' },
  consistent: { label: 'Fits the image', color: 'teal' },
  cannot_tell: { label: "Can't tell from the image", color: 'gray' },
};

function CaptionChecks({ checks }: { checks: CaptionCheck[] }) {
  return (
    <div className="caption-checks">
      <h4>Caption compared with the image</h4>
      <p className="muted small">
        Model visual assessment from visible details. It is not evidence and does not settle the
        claim.
      </p>
      <ul>
        {checks.map((check) => {
          const status = CHECK[check.assessment];
          return (
            <li key={check.caption_detail}>
              <div className="caption-check-head">
                <span dir="auto">{check.caption_detail}</span>
                <Badge variant="light" color={status.color} tt="none" size="sm">
                  {status.label}
                </Badge>
              </div>
              {!!check.visible_basis.length && (
                <ul className="caption-check-basis">
                  {check.visible_basis.map((text) => (
                    <li key={text} dir="auto">
                      {text}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function PriorChecks({ checks }: { checks: NonNullable<MediaFinding['prior_checks']> }) {
  return (
    <div className="prior-checks">
      <h4>Published fact checks of this image</h4>
      {checks.status === 'found' && (
        <>
          <ul>
            {checks.reviews.map((review: PriorFactCheck) => {
              const url = safeUrl(review.url);
              if (!url) return null;
              const meta = [review.publisher ?? review.site, formatDate(review.review_date)]
                .filter(Boolean)
                .join(' · ');
              return (
                <li key={url}>
                  <a href={url} target="_blank" rel="noopener noreferrer" dir="auto">
                    {plainTitle(review.title, url)} <ArrowUpRight size={13} aria-hidden />
                  </a>
                  <div className="prior-check-meta">
                    {meta && <span className="muted small">{meta}</span>}
                    {review.rating && (
                      <span className="small" dir="auto">
                        Publisher&rsquo;s rating: <strong>{review.rating}</strong>
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="muted small">
            Ratings are each publisher&rsquo;s own conclusion about the claim they reviewed, which
            may differ from this post. They are read as sources below, not adopted as a verdict.
          </p>
        </>
      )}
      {checks.status === 'none' && (
        <p className="muted">No published fact check of this image was found.</p>
      )}
      {(checks.status === 'not_checked' || checks.status === 'failed') && (
        <p className="muted">{checks.reason ?? 'Not checked.'}</p>
      )}
    </div>
  );
}

type Match = MediaFinding['origin']['matches'][number];

function MatchList({ matches }: { matches: Match[] }) {
  return (
    <ul className="media-matches">
      {matches.map((match) => {
        const url = safeUrl(match.page_url);
        if (!url) return null;
        const meta = [match.source, match.date_text].filter(Boolean).join(' · ');
        return (
          <li key={url}>
            <a href={url} target="_blank" rel="noopener noreferrer" dir="auto">
              {plainTitle(match.page_title, url)} <ArrowUpRight size={13} aria-hidden />
            </a>
            {meta && <span className="muted small">{meta}</span>}
          </li>
        );
      })}
    </ul>
  );
}

function Origin({ origin }: { origin: MediaFinding['origin'] }) {
  const same = origin.matches.filter((match) => match.match !== 'similar');
  const similar = origin.matches.filter((match) => match.match === 'similar').slice(0, 5);
  // The adapter lists dated same-image matches earliest first.
  const earliest = same.find((match) => match.published_on && safeUrl(match.page_url));
  return (
    <div className="media-origin">
      <h4>Where else this image appears</h4>
      {origin.status === 'not_checked' && (
        <p>
          {origin.reason ?? 'Not checked.'} The image&rsquo;s original source and date remain
          unresolved.
        </p>
      )}
      {origin.status === 'failed' && <p>{origin.reason ?? 'The search did not complete.'}</p>}
      {origin.status === 'no_matches' && (
        <p>No matching pages were found. That does not show the image is original.</p>
      )}
      {origin.status === 'matches_found' && (
        <>
          {earliest && (
            <p className="earliest-match">
              Earliest dated page found: <strong>{earliest.source ?? 'Unknown site'}</strong>,{' '}
              {earliest.date_text}
            </p>
          )}
          {!!same.length && (
            <>
              <p className="match-group">Same image ({same.length})</p>
              <MatchList matches={same} />
            </>
          )}
          {!!similar.length && (
            <>
              <p className="match-group">Similar images</p>
              <MatchList matches={similar} />
            </>
          )}
          <p className="muted small">
            Dates are the ones the search provider shows for each page. A match shows where the
            image appears online; it does not prove where or when it was first published.
          </p>
        </>
      )}
      {!!origin.best_guess_labels.length && (
        <p className="muted small">Search topic guess: {origin.best_guess_labels.join(', ')}</p>
      )}
    </div>
  );
}

export function MediaFindings({ media }: { media: MediaFinding[] }) {
  return (
    <section className="media-findings" aria-labelledby="media-heading">
      <div className="section-heading">
        <h2 id="media-heading">Images and video</h2>
        <span>
          {media.length} {media.length === 1 ? 'file' : 'files'}
        </span>
      </div>
      {media.map((item, index) => {
        const status = ANALYSIS[item.analysis.status];
        const src = `/api/media/${encodeURIComponent(item.id)}`;
        return (
          <article className="media-card" key={item.id}>
            <div className="media-thumb">
              {item.kind === 'image' ? (
                <img src={src} alt={`Uploaded image ${index + 1}: ${item.filename}`} />
              ) : (
                <video
                  src={src}
                  controls
                  preload="metadata"
                  aria-label={`Uploaded video ${index + 1}: ${item.filename}`}
                />
              )}
            </div>
            <div className="media-body">
              <div className="media-title">
                <strong title={item.filename}>{item.filename}</strong>
                <Badge variant="light" color={status.color} tt="none">
                  {status.label}
                </Badge>
              </div>
              {item.analysis.note && <p className="muted">{item.analysis.note}</p>}
              {item.analysis.visible_text && (
                <div>
                  <h4>Text read from the image</h4>
                  <p className="muted small">Model transcription; compare it with the image.</p>
                  <blockquote className="visible-text" dir="auto">
                    {item.analysis.visible_text}
                  </blockquote>
                  {item.analysis.claim_text && (
                    <p className="muted small">
                      {item.analysis.claim_text.length
                        ? `Checked as claims: ${item.analysis.claim_text.join(' / ')}`
                        : 'No statements to check; signs, labels and stamps are treated as details.'}
                    </p>
                  )}
                </div>
              )}
              {!!item.analysis.caption_checks?.length && (
                <CaptionChecks checks={item.analysis.caption_checks} />
              )}
              {!!item.analysis.observations.length && (
                <div>
                  <h4>What the image shows</h4>
                  <ul>
                    {item.analysis.observations.map((text) => (
                      <li key={text} dir="auto">
                        {text}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {!!item.analysis.context_cues.length && (
                <div>
                  <h4>Details to check</h4>
                  <p className="muted small">Visible cues about place or time, not conclusions.</p>
                  <ul>
                    {item.analysis.context_cues.map((text) => (
                      <li key={text} dir="auto">
                        {text}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {item.prior_checks && <PriorChecks checks={item.prior_checks} />}
              <Origin origin={item.origin} />
            </div>
          </article>
        );
      })}
    </section>
  );
}
