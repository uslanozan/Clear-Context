import { useRef, useState } from 'react';
import { Alert, Button, SegmentedControl, Textarea } from '@mantine/core';
import { ArrowUpRight, ArrowRight, ImagePlus, Paperclip, X } from 'lucide-react';
import type { Health, ResearchMode } from '../lib/types';
import { RESEARCH_MODES } from '../lib/modes';
import { formatBytes, MEDIA_ACCEPT, useMediaAttachments } from '../lib/media';
import { ProcessTimeline } from './ProcessTimeline';
import { MediaPreview } from './MediaPreview';

export const EXAMPLES = [
  {
    title: 'A date. A number. Two claims.',
    text: 'The fictional Cedar Observatory opened on 12 May 2024. It has three telescopes.',
  },
  {
    title: 'The small print matters.',
    text: 'The fictional museum offers free entry only to students aged 18 or over on Tuesdays. Entry is not free on other days.',
  },
];
interface Props {
  initialText?: string;
  health?: Health;
  isPending: boolean;
  error: Error | null;
  onSubmit: (text: string, researchMode?: ResearchMode) => Promise<void>;
}

export function Composer({ initialText = '', health, isPending, error, onSubmit }: Props) {
  const [text, setText] = useState(initialText);
  const [researchMode, setResearchMode] = useState<ResearchMode>('balanced');
  const [validation, setValidation] = useState('');
  const [dragging, setDragging] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const media = useMediaAttachments();
  const count = text.trim().length;
  async function submit() {
    if (isPending || submitting.current || media.attachments.length) return;
    if (!count || count > 20000) {
      setValidation('Enter between 1 and 20,000 characters.');
      textarea.current?.focus();
      return;
    }
    if (!health) return;
    submitting.current = true;
    setValidation('');
    try {
      await onSubmit(text.trim(), health.research_enabled ? researchMode : undefined);
    } catch {
      submitting.current = false;
    }
  }
  return (
    <div className="intake-page">
      <header className="intake-heading">
        <div>
          <h1>Check the context</h1>
          <p>Add a claim and the material behind it.</p>
        </div>
        <div className="muse-reference">
          <img
            src="/brand/muse-jolly.jpg"
            alt="Jolly, the Muse mascot, at a laptop"
            width="1200"
            height="630"
          />
          <div>
            <img src="/brand/meta.svg" alt="Meta" width="68" height="15" />
            <span>Built with Muse</span>
          </div>
        </div>
      </header>
      <div className="intake-grid">
        <div className="intake-main">
          <form
            className={`intake-form ${dragging ? 'is-dragging' : ''}`}
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
            onPaste={(event) => {
              const files = Array.from(event.clipboardData.files);
              if (!files.length) return;
              event.preventDefault();
              media.add(files);
              const pastedText = event.clipboardData.getData('text/plain');
              if (pastedText)
                setText((previous) =>
                  `${previous}${previous ? '\n' : ''}${pastedText}`.slice(0, 20000),
                );
            }}
            onDragOver={(event) => {
              if (Array.from(event.dataTransfer.types).includes('Files')) {
                event.preventDefault();
                setDragging(true);
              }
            }}
            onDragLeave={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null))
                setDragging(false);
            }}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              media.add(Array.from(event.dataTransfer.files));
            }}
          >
            <label className="input-label" htmlFor="passage-input">
              What would you like to check?
            </label>
            <Textarea
              id="passage-input"
              ref={textarea}
              aria-label="Passage to investigate"
              aria-describedby="input-description"
              placeholder="Paste a claim, add a screenshot, or drop a video..."
              value={text}
              onChange={(event) => {
                setText(event.currentTarget.value);
                setValidation('');
              }}
              minRows={5}
              maxRows={12}
              autosize
              maxLength={20000}
              classNames={{ root: 'passage-field', input: 'passage-input' }}
              error={validation || undefined}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                  event.preventDefault();
                  void submit();
                }
              }}
            />
            {!!media.attachments.length && (
              <ul className="attachment-list" aria-label="Attached media">
                {media.attachments.map((item) => (
                  <li className="attachment" key={item.id}>
                    <button
                      className="attachment-remove icon-button"
                      type="button"
                      aria-label={`Remove ${item.file.name}`}
                      onClick={() => media.remove(item.id)}
                    >
                      <X size={16} />
                    </button>
                    <MediaPreview attachment={item} />
                    <div>
                      <strong title={item.file.name}>{item.file.name}</strong>
                      <span>
                        {item.kind === 'video' ? 'Video' : 'Image'} · {formatBytes(item.file.size)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {dragging && (
              <div className="drop-overlay">
                <ImagePlus size={26} />
                <strong>Drop images or videos here</strong>
              </div>
            )}
            <div className="intake-toolbar">
              <Button
                type="button"
                variant="subtle"
                color="gray"
                leftSection={<Paperclip size={17} />}
                onClick={() => fileInput.current?.click()}
              >
                Attach media
              </Button>
              <span>
                {count ? `${count.toLocaleString('en-US')} / 20,000` : 'Ctrl + Enter to start'}
              </span>
              <Button
                type="submit"
                loading={isPending}
                disabled={!health || !count || !!media.attachments.length}
                rightSection={<ArrowRight size={16} />}
              >
                Start investigation
              </Button>
            </div>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept={MEDIA_ACCEPT}
              className="visually-hidden"
              aria-label="Attach images or videos"
              onChange={(event) => {
                media.add(Array.from(event.currentTarget.files || []));
                event.currentTarget.value = '';
              }}
            />
          </form>
          {health?.research_enabled && (
            <div className="research-mode">
              <span className="research-mode-label" id="research-mode-label">
                Research depth
              </span>
              <SegmentedControl
                aria-labelledby="research-mode-label"
                value={researchMode}
                onChange={(value) => setResearchMode(value as ResearchMode)}
                data={RESEARCH_MODES.map(({ value, label }) => ({ value, label }))}
              />
              <p className="research-mode-detail">
                {RESEARCH_MODES.find((mode) => mode.value === researchMode)?.detail}
              </p>
            </div>
          )}
          <p className="input-description" id="input-description">
            Paste or drop images and videos, or choose files. Up to 4 files · Images 20 MB · Videos
            100 MB · Total 100 MB.
          </p>
          {media.error && (
            <Alert color="red" title="Some files weren't added" role="alert">
              {media.error}
            </Alert>
          )}
          {!!media.attachments.length && (
            <div className="media-notice" role="status">
              <strong>Media preview only</strong>
              <p>
                These files stay in this tab. Image and video analysis is not connected yet, so they
                won't be submitted.
              </p>
              <Button type="button" size="xs" variant="default" onClick={() => media.remove()}>
                Remove media{count ? ' and use text' : ''}
              </Button>
            </div>
          )}
          {error && (
            <Alert color="red" title="We couldn't start this investigation" role="alert">
              {error.message} Nothing will be submitted again automatically.
            </Alert>
          )}
          <p className="privacy-note">
            {health?.mode === 'meta'
              ? health.research_enabled
                ? 'Text is sent to Meta; generated search queries and source URLs are sent to Tavily. Saved reports stay on your server.'
                : 'Text is sent to Meta when you start. Source research is disabled. Saved reports stay on your server.'
              : health?.mode === 'mock'
                ? 'Preview mode. No model calls or credits used.'
                : 'Waiting for your investigation service.'}
          </p>
          <section className="example-section">
            <h2>Try a text example</h2>
            {EXAMPLES.map((example) => (
              <button
                type="button"
                key={example.title}
                onClick={() => {
                  setText(example.text);
                  setValidation('');
                  textarea.current?.focus();
                }}
              >
                {example.title}
                <ArrowUpRight size={15} />
              </button>
            ))}
          </section>
        </div>
        <aside className="intake-aside">
          <ProcessTimeline planned researchEnabled={Boolean(health?.research_enabled)} />
        </aside>
      </div>
    </div>
  );
}
