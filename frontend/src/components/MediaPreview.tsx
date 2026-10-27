import { useState } from 'react';
import { FileVideo, ImageOff } from 'lucide-react';
import type { Attachment } from '../lib/media';

export function MediaPreview({ attachment }: { attachment: Attachment }) {
  const [failed, setFailed] = useState(false);
  const label = `Preview of ${attachment.file.name}`;
  if (failed)
    return (
      <div className="preview-unavailable" role="status">
        {attachment.kind === 'video' ? (
          <FileVideo size={22} aria-hidden="true" />
        ) : (
          <ImageOff size={22} aria-hidden="true" />
        )}
        <span>This browser cannot preview this file. Remove it or try another format.</span>
      </div>
    );
  return attachment.kind === 'image' ? (
    <img src={attachment.url} alt={label} onError={() => setFailed(true)} />
  ) : (
    <video
      src={attachment.url}
      controls
      playsInline
      preload="metadata"
      aria-label={label}
      onError={() => setFailed(true)}
    />
  );
}
