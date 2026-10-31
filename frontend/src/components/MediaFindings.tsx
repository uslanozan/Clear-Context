import { useRef } from 'react';
import { Badge } from '@mantine/core';
import { ArrowUpRight } from 'lucide-react';
import type { CaptionCheck, MediaFinding, PriorFactCheck, SpeechTurn } from '../lib/types';

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

type Noun = 'image' | 'video';

function checkLabels(
  noun: Noun,
): Record<CaptionCheck['assessment'], { label: string; color: string }> {
  return {
    inconsistent: { label: `Does not fit the ${noun}`, color: 'orange' },
    consistent: { label: `Fits the ${noun}`, color: 'teal' },
    cannot_tell: { label: `Can't tell from the ${noun}`, color: 'gray' },
  };
}

/** Seconds as m:ss, the way video players show positions. */
export function clock(seconds: number) {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

function CaptionChecks({ checks, noun }: { checks: CaptionCheck[]; noun: Noun }) {
  const labels = checkLabels(noun);
  return (
    <div className="caption-checks">
      <h4>Caption compared with the {noun}</h4>
      <p className="muted small">
        Model visual assessment from visible details. It is not evidence and does not settle the
        claim.
      </p>
      <ul>
        {checks.map((check) => {
          const status = labels[check.assessment];
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

function PriorChecks({
  checks,
  noun,
}: {
  checks: NonNullable<MediaFinding['prior_checks']>;
  noun: Noun;
}) {
  return (
    <div className="prior-checks">
      <h4>Published fact checks of this {noun}</h4>
      {checks.status === 'found' && (
        <>
          <ul>
            {checks.reviews.map((review: PriorFactCheck) => {
              const url = safeUrl(review.url);
              if (!url) return null;
              const meta = [
                review.publisher ?? review.site,
                formatDate(review.review_date),
                review.matched_by === 'text' ? 'matched by the caption text' : null,
              ]
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
            may differ from this post. A review matched by the caption text may concern another
            picture. They are read as sources below, not adopted as a verdict.
          </p>
        </>
      )}
      {checks.status === 'none' && (
        <p className="muted">No published fact check of this {noun} was found.</p>
      )}
      {(checks.status === 'not_checked' || checks.status === 'failed') && (
        <p className="muted">{checks.reason ?? 'Not checked.'}</p>
      )}
    </div>
  );
}

type Match = MediaFinding['origin']['matches'][number];

function MatchList({ matches, onSeek }: { matches: Match[]; onSeek?: (at: number) => void }) {
  return (
    <ul className="media-matches">
      {matches.map((match) => {
        const url = safeUrl(match.page_url);
        if (!url) return null;
        const engine = match.found_by === 'bing' ? 'via Bing' : null;
        const meta = [match.source, match.date_text, engine].filter(Boolean).join(' · ');
        const frameAt = match.frame_at;
        return (
          <li key={url}>
            <a href={url} target="_blank" rel="noopener noreferrer" dir="auto">
              {plainTitle(match.page_title, url)} <ArrowUpRight size={13} aria-hidden />
            </a>
            {meta && <span className="muted small">{meta}</span>}
            {frameAt != null && onSeek && (
              <button type="button" className="time-link" onClick={() => onSeek(frameAt)}>
                frame at {clock(frameAt)}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Origin({
  origin,
  noun,
  onSeek,
}: {
  origin: MediaFinding['origin'];
  noun: Noun;
  onSeek?: (at: number) => void;
}) {
  const same = origin.matches.filter((match) => match.match !== 'similar');
  const similar = origin.matches.filter((match) => match.match === 'similar').slice(0, 5);
  // The adapter lists dated same-image matches earliest first.
  const earliest = same.find((match) => match.published_on && safeUrl(match.page_url));
  return (
    <div className="media-origin">
      <h4>
        {noun === 'video' ? 'Where frames of this video appear' : 'Where else this image appears'}
      </h4>
      {origin.status === 'not_checked' && (
        <p>
          {origin.reason ?? 'Not checked.'} The {noun}&rsquo;s original source and date remain
          unresolved.
        </p>
      )}
      {origin.status === 'failed' && <p>{origin.reason ?? 'The search did not complete.'}</p>}
      {origin.status === 'no_matches' && (
        <p>No matching pages were found. That does not show the {noun} is original.</p>
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
              <p className="match-group">
                {noun === 'video' ? 'Same frame' : 'Same image'} ({same.length})
              </p>
              <MatchList matches={same} onSeek={onSeek} />
            </>
          )}
          {!!similar.length && (
            <>
              <p className="match-group">Similar images</p>
              <MatchList matches={similar} onSeek={onSeek} />
            </>
          )}
          <p className="muted small">
            Dates are the ones the search provider shows for each page. A match shows where the
            {noun === 'video' ? ' frame' : ' image'} appears online; it does not prove where or when
            it was first published.
          </p>
        </>
      )}
      {!!origin.best_guess_labels.length && (
        <p className="muted small">Search topic guess: {origin.best_guess_labels.join(', ')}</p>
      )}
    </div>
  );
}

function Speech({ turns, onSeek }: { turns: SpeechTurn[]; onSeek: (at: number) => void }) {
  return (
    <div>
      <h4>What is said</h4>
      <p className="muted small">
        Transcribed by a speech model; words and speaker labels can be wrong, and labels such as A
        or B are not identities. Check quotes against the video.
      </p>
      <ol className="speech-turns">
        {turns.map((turn) => (
          <li key={`${turn.start}-${turn.text}`}>
            <button type="button" className="time-link" onClick={() => onSeek(turn.start)}>
              {clock(turn.start)}–{clock(turn.end)}
            </button>
            {turn.speaker && <span className="muted small">{turn.speaker}</span>}
            <span dir="auto">{turn.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function MediaCard({ item, index }: { item: MediaFinding; index: number }) {
  const player = useRef<HTMLVideoElement>(null);
  const status = ANALYSIS[item.analysis.status];
  const src = `/api/media/${encodeURIComponent(item.id)}`;
  const noun: Noun = item.kind;
  const analysis = item.analysis;
  const onScreen = analysis.on_screen_text ?? [];
  const seek = (at: number) => {
    if (!player.current) return;
    player.current.currentTime = at;
    player.current.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
  };
  return (
    <article className="media-card">
      <div className="media-thumb">
        {item.kind === 'image' ? (
          <img src={src} alt={`Uploaded image ${index + 1}: ${item.filename}`} />
        ) : (
          <video
            ref={player}
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
        {item.source_url && safeUrl(item.source_url) && (
          <p className="muted small">
            Main image of{' '}
            <a href={safeUrl(item.source_url)!} target="_blank" rel="noopener noreferrer">
              {new URL(item.source_url).hostname.replace(/^www\./, '')}
            </a>
            ; it may be a stock or file photo, so it is checked on its own.
          </p>
        )}
        {analysis.note && <p className="muted">{analysis.note}</p>}
        {!!analysis.speech?.length && <Speech turns={analysis.speech} onSeek={seek} />}
        {item.kind === 'video' && !!onScreen.length && (
          <div>
            <h4>Text shown in the video</h4>
            <p className="muted small">Model transcription; compare it with the video.</p>
            <ul className="speech-turns">
              {onScreen.map((line) => (
                <li key={`${line.at}-${line.text}`}>
                  {line.at != null && (
                    <button type="button" className="time-link" onClick={() => seek(line.at!)}>
                      {clock(line.at)}
                    </button>
                  )}
                  <span dir="auto">{line.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {item.kind === 'image' && analysis.visible_text && (
          <div>
            <h4>Text read from the image</h4>
            <p className="muted small">Model transcription; compare it with the image.</p>
            <blockquote className="visible-text" dir="auto">
              {analysis.visible_text}
            </blockquote>
          </div>
        )}
        {analysis.claim_text && (analysis.visible_text || onScreen.length > 0) && (
          <p className="muted small">
            {analysis.claim_text.length
              ? `Checked as claims: ${analysis.claim_text.join(' / ')}`
              : 'No statements to check; signs, labels and stamps are treated as details.'}
          </p>
        )}
        {!!analysis.caption_checks?.length && (
          <CaptionChecks checks={analysis.caption_checks} noun={noun} />
        )}
        {!!analysis.observations.length && (
          <div>
            <h4>What the {noun} shows</h4>
            <ul>
              {analysis.observations.map((text) => (
                <li key={text} dir="auto">
                  {text}
                </li>
              ))}
            </ul>
          </div>
        )}
        {!!analysis.context_cues.length && (
          <div>
            <h4>Details to check</h4>
            <p className="muted small">Cues about place or time, not conclusions.</p>
            <ul>
              {analysis.context_cues.map((text) => (
                <li key={text} dir="auto">
                  {text}
                </li>
              ))}
            </ul>
          </div>
        )}
        {!!item.frames?.length && (
          <div>
            <h4>Frames searched</h4>
            <ul className="video-frames">
              {item.frames.map((frame, frameIndex) => (
                <li key={frame.at}>
                  <button type="button" onClick={() => seek(frame.at)}>
                    <img
                      src={`${src}/frames/${frameIndex}`}
                      alt={`Frame at ${clock(frame.at)}`}
                      loading="lazy"
                    />
                    <span className="small">
                      {clock(frame.at)} ·{' '}
                      {frame.chosen_by === 'model' ? 'distinctive moment' : 'scene change'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {item.prior_checks && <PriorChecks checks={item.prior_checks} noun={noun} />}
        <Origin
          origin={item.origin}
          noun={noun}
          onSeek={item.kind === 'video' ? seek : undefined}
        />
      </div>
    </article>
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
      {media.map((item, index) => (
        <MediaCard key={item.id} item={item} index={index} />
      ))}
    </section>
  );
}
