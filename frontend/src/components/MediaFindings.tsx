import { Badge } from '@mantine/core';
import { ArrowUpRight } from 'lucide-react';
import type { MediaFinding } from '../lib/types';

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

function Origin({ origin }: { origin: MediaFinding['origin'] }) {
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
          <ul className="media-matches">
            {origin.matches.map((match) => {
              const url = safeUrl(match.page_url);
              return url ? (
                <li key={url}>
                  <a href={url} target="_blank" rel="noopener noreferrer">
                    {plainTitle(match.page_title, url)} <ArrowUpRight size={13} aria-hidden />
                  </a>
                  <Badge variant="light" color="gray" tt="none" size="sm">
                    {match.match === 'full' ? 'Same image' : 'Similar image'}
                  </Badge>
                </li>
              ) : null;
            })}
          </ul>
          <p className="muted small">
            A match shows where the image appears online. It does not prove where or when it was
            first published.
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
                </div>
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
              <Origin origin={item.origin} />
            </div>
          </article>
        );
      })}
    </section>
  );
}
