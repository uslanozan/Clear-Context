import { useRef, useState } from 'react';
import { Alert, Button, SegmentedControl, Textarea } from '@mantine/core';
import { ArrowRight, ImagePlus, Paperclip, X } from 'lucide-react';
import type { Health, ResearchMode } from '../lib/types';
import { RESEARCH_MODES } from '../lib/modes';
import { formatBytes, MEDIA_ACCEPT, useMediaAttachments } from '../lib/media';
import { ProcessTimeline } from './ProcessTimeline';
import { MediaPreview } from './MediaPreview';

interface Props {
  initialText?: string;
  health?: Health;
  isPending: boolean;
  error: Error | null;
  onSubmit: (text: string, researchMode: ResearchMode | undefined, files: File[]) => Promise<void>;
}

export function Composer({ initialText = '', health, isPending, error, onSubmit }: Props) {
  const [text, setText] = useState(initialText);
  // Until the user picks a depth, the default from settings applies.
  const [chosenMode, setResearchMode] = useState<ResearchMode | null>(null);
  const researchMode = chosenMode ?? health?.default_research_mode ?? 'balanced';
  const [validation, setValidation] = useState('');
  const [dragging, setDragging] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const media = useMediaAttachments();
  const count = text.trim().length;
  const hasMedia = media.attachments.length > 0;
  const hasVideo = media.attachments.some((item) => item.kind === 'video');
  async function submit() {
    if (isPending || submitting.current) return;
    if ((!count && !hasMedia) || count > 20000) {
      setValidation('Enter up to 20,000 characters or attach an image or video.');
      textarea.current?.focus();
      return;
    }
    if (!health) return;
    submitting.current = true;
    setValidation('');
    try {
      await onSubmit(
        text.trim(),
        health.research_enabled ? researchMode : undefined,
        media.attachments.map((item) => item.file),
      );
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
              placeholder="Paste a claim or a link, add a screenshot, or drop a video..."
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
                disabled={!health || (!count && !hasMedia)}
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
              {/* The selected pill shows glass that breaks into more pieces with more depth. */}
              <div className="depth-control" data-depth={researchMode}>
                <SegmentedControl
                  aria-labelledby="research-mode-label"
                  value={researchMode}
                  onChange={(value) => setResearchMode(value as ResearchMode)}
                  data={RESEARCH_MODES.map(({ value, label }) => ({ value, label }))}
                />
              </div>
              <p className="research-mode-detail">
                {RESEARCH_MODES.find((mode) => mode.value === researchMode)?.detail}
              </p>
            </div>
          )}
          {media.error && (
            <Alert color="red" title="Some files weren't added" role="alert">
              {media.error}
            </Alert>
          )}
          {!!media.attachments.length && (
            <div className="media-notice" role="status">
              <strong>Files are sent with your text</strong>
              <p>
                {health?.mode === 'mock'
                  ? 'Preview mode stores the files but does not analyze them.'
                  : 'A Muse model reads visible text in images and describes them. It does not decide where or when a photo was taken.'}
                {hasVideo &&
                  health?.mode !== 'mock' &&
                  ' Videos up to 50 MB and 10 minutes: speech is transcribed by a speech model, the frames are described and three frames are searched for earlier copies.'}
              </p>
              <Button type="button" size="xs" variant="default" onClick={() => media.remove()}>
                Remove media{count ? ' and use text only' : ''}
              </Button>
            </div>
          )}
          {error && (
            <Alert color="red" title="We couldn't start this investigation" role="alert">
              {error.message} Nothing will be submitted again automatically.
            </Alert>
          )}
        </div>
        <aside className="intake-aside">
          <ProcessTimeline planned researchEnabled={Boolean(health?.research_enabled)} />
        </aside>
      </div>
    </div>
  );
}
