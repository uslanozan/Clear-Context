import { useEffect, useState } from 'react';
import { Alert, Button, Checkbox, Loader, SegmentedControl, Textarea } from '@mantine/core';
import { ArrowUpRight, Check, CircleAlert, LoaderCircle } from 'lucide-react';
import { failureMessage } from '../../src/lib/api';
import { RESEARCH_MODES } from '../../src/lib/modes';
import { stageTitle } from '../../src/lib/stages';
import type { Investigation, ResearchMode, ResearchStep } from '../../src/lib/types';
import { MAX_TEXT, readablePage, submissionText, type PendingCapture } from './capture-model';
import { ServerError, serverApi } from './server-api';
import { ServerLine, useConnection, type Connection } from './ServerLine';
import { clearPending, loadPending, loadServer } from './storage';

const KIND_LABEL: Record<PendingCapture['kind'], string> = {
  text: 'Selected text',
  image: 'Image from the page',
  video: 'Video frame from the page',
  area: 'Selected area of the page',
};

export function CaptureApp() {
  const [capture, setCapture] = useState<PendingCapture | null | undefined>(undefined);
  const [server, setServer] = useState<string | null>(null);
  const connection = useConnection(server);
  const [started, setStarted] = useState<Investigation | null>(null);

  useEffect(() => {
    void Promise.all([loadPending(), loadServer()]).then(([pending, origin]) => {
      setCapture(pending);
      setServer(origin);
    });
  }, []);

  return (
    <main className="ext-page">
      <header className="ext-header">
        <span className="brand-icon" aria-hidden="true">
          <img src="icons/icon-32.png" alt="" width={20} height={20} />
        </span>
        <div>
          <strong>Clear Context</strong>
          {server && (
            <ServerLine
              server={server}
              connection={connection}
              onChange={(origin) => setServer(origin)}
            />
          )}
        </div>
      </header>
      {started && server ? (
        <Status
          server={server}
          investigation={started}
          onNew={() => {
            setStarted(null);
            setCapture(null);
          }}
        />
      ) : capture === undefined ? (
        <div className="ext-center">
          <Loader size="sm" />
        </div>
      ) : capture === null ? (
        <div className="ext-empty">
          <h1>Nothing captured yet</h1>
          <p>
            Select text and right-click it, right-click an image or a video, or use{' '}
            <strong>Capture an area</strong> from the toolbar button.
          </p>
        </div>
      ) : (
        <Preview capture={capture} server={server} connection={connection} onStarted={setStarted} />
      )}
    </main>
  );
}

function Preview({
  capture,
  server,
  connection,
  onStarted,
}: {
  capture: PendingCapture;
  server: string | null;
  connection: Connection;
  onStarted: (investigation: Investigation) => void;
}) {
  const health = connection.state === 'ready' ? connection.health : null;
  const [text, setText] = useState(capture.text);
  const [includePage, setIncludePage] = useState(
    capture.kind === 'text' && readablePage(capture.pageUrl),
  );
  const [chosenMode, setMode] = useState<ResearchMode | null>(null);
  const [image, setImage] = useState(capture.image);
  const [fullSize, setFullSize] = useState<'idle' | 'loading' | 'done' | 'failed'>('idle');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const mode = chosenMode ?? health?.default_research_mode ?? 'balanced';
  const body = submissionText(text, capture.pageUrl, includePage);

  async function useFullSize() {
    if (!capture.sourceUrl) return;
    setFullSize('loading');
    try {
      const origin = new URL(capture.sourceUrl).origin;
      const granted = await chrome.permissions.request({ origins: [`${origin}/*`] });
      if (!granted) throw new Error('not granted');
      const response = await fetch(capture.sourceUrl, { credentials: 'omit' });
      const blob = await response.blob();
      if (!response.ok || !blob.type.startsWith('image/') || blob.size > 20 * 2 ** 20) {
        throw new Error('not an image');
      }
      const reader = new FileReader();
      reader.onload = () => {
        setImage(String(reader.result));
        setFullSize('done');
      };
      reader.readAsDataURL(blob);
    } catch {
      // The cropped screenshot stays in use.
      setFullSize('failed');
    }
  }

  async function submit() {
    if (!server || submitting) return;
    if (!body && !image) {
      setError('Add text to check, or capture an image.');
      return;
    }
    if (body.length > MAX_TEXT) {
      setError('Use up to 20,000 characters.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const created = await serverApi.start(server, {
        text: body,
        image,
        mode: health?.research_enabled ? mode : undefined,
      });
      await clearPending();
      onStarted(created);
    } catch (failure) {
      // Nothing is retried automatically; the capture and text stay for another try.
      setError(failure instanceof ServerError ? failure.message : 'The request could not start.');
      setSubmitting(false);
    }
  }

  return (
    <form
      className="ext-preview"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <p className="ext-kind">{KIND_LABEL[capture.kind]}</p>
      {capture.error && (
        <Alert color="orange" icon={<CircleAlert size={16} />} title="The capture didn't work">
          {capture.error} Try <strong>Capture an area</strong> from the toolbar button, or add the
          text below.
        </Alert>
      )}
      {image && (
        <figure className="ext-image">
          <img src={image} alt="Captured picture to check" />
          <figcaption className="muted small">
            {fullSize === 'done'
              ? 'Full-size image from the page.'
              : 'Cropped from what was on screen.'}{' '}
            {capture.sourceUrl && fullSize !== 'done' && (
              <button
                type="button"
                className="text-button"
                disabled={fullSize === 'loading'}
                onClick={() => void useFullSize()}
              >
                {fullSize === 'loading' ? 'Loading…' : 'Use the full-size image'}
              </button>
            )}
            {fullSize === 'failed' && ' The full-size image could not be loaded.'}
          </figcaption>
        </figure>
      )}
      <Textarea
        label={capture.kind === 'text' ? 'Text to check' : 'Caption or post text'}
        description={
          capture.kind === 'text'
            ? 'You can edit it before sending.'
            : 'Optional: what the post says about this picture.'
        }
        autosize
        minRows={capture.kind === 'text' ? 5 : 3}
        maxRows={12}
        value={text}
        onChange={(event) => setText(event.currentTarget.value)}
      />
      {readablePage(capture.pageUrl) && (
        <Checkbox
          label="Also read this page"
          description={capture.pageTitle || new URL(capture.pageUrl).host}
          checked={includePage}
          onChange={(event) => setIncludePage(event.currentTarget.checked)}
        />
      )}
      {health?.research_enabled && (
        <div>
          <span className="settings-label" id="ext-mode-label">
            Research depth
          </span>
          <SegmentedControl
            fullWidth
            aria-labelledby="ext-mode-label"
            value={mode}
            onChange={(value) => setMode(value as ResearchMode)}
            data={RESEARCH_MODES.map(({ value, label }) => ({ value, label }))}
          />
        </div>
      )}
      {connection.state === 'unreachable' && (
        <Alert
          color="orange"
          icon={<CircleAlert size={16} />}
          title="Clear Context isn't reachable"
        >
          Start the app, or change the address above. Your capture is kept.
        </Alert>
      )}
      {error && (
        <Alert color="red" role="alert">
          {error}
        </Alert>
      )}
      <Button
        type="submit"
        fullWidth
        loading={submitting}
        disabled={connection.state !== 'ready' || (!body && !image)}
      >
        Investigate
      </Button>
      {health && (
        <p className="muted small">
          {health.mode === 'meta'
            ? 'Starting uses model calls and search credits on your server.'
            : 'Preview mode makes no model calls.'}
        </p>
      )}
    </form>
  );
}

function Status({
  server,
  investigation,
  onNew,
}: {
  server: string;
  investigation: Investigation;
  onNew: () => void;
}) {
  const [current, setCurrent] = useState(investigation);
  const [steps, setSteps] = useState<ResearchStep[]>([]);
  const [offline, setOffline] = useState(false);
  const done = current.status === 'completed' || current.status === 'failed';

  useEffect(() => {
    if (done) return;
    const timer = window.setInterval(async () => {
      try {
        const [latest, recorded] = await Promise.all([
          serverApi.investigation(server, investigation.id),
          serverApi.steps(server, investigation.id),
        ]);
        setCurrent(latest);
        setSteps(recorded);
        setOffline(false);
      } catch {
        setOffline(true);
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [done, server, investigation.id]);

  // Recorded events only, in the order they happened; no invented progress.
  const titles = Array.from(
    new Set(steps.map((step) => stageTitle(step.name)).filter((t): t is string => !!t)),
  );
  const report = `${server}/investigations/${encodeURIComponent(investigation.id)}`;
  return (
    <section className="ext-status" aria-live="polite">
      <h1>
        {current.status === 'completed'
          ? 'Report ready'
          : current.status === 'failed'
            ? 'The investigation stopped'
            : 'Investigating'}
      </h1>
      {current.status === 'failed' && <p>{failureMessage(current.error_code)}</p>}
      <ol className="ext-steps">
        {titles.map((title, index) => {
          const active = !done && index === titles.length - 1;
          return (
            <li key={title} className={active ? 'active' : ''}>
              {active ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />}
              {title}
            </li>
          );
        })}
        {!titles.length && !done && <li className="muted">Waiting for the first step…</li>}
      </ol>
      {offline && (
        <p className="muted small">Status is unavailable right now; the investigation continues.</p>
      )}
      <Button
        fullWidth
        rightSection={<ArrowUpRight size={15} />}
        onClick={() => void chrome.tabs.create({ url: report })}
      >
        Open report
      </Button>
      <Button fullWidth variant="default" onClick={onNew}>
        Check something else
      </Button>
    </section>
  );
}
