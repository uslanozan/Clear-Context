import { useEffect, useRef, useState } from 'react';

export const MEDIA_LIMITS = {
  count: 4,
  imageBytes: 20 * 1024 * 1024,
  videoBytes: 100 * 1024 * 1024,
  totalBytes: 100 * 1024 * 1024,
};
// The backend checks file signatures and accepts these formats only.
export const MEDIA_ACCEPT = 'image/png,image/jpeg,image/webp,image/gif,video/mp4';
export interface Attachment {
  id: string;
  file: File;
  url: string;
  kind: 'image' | 'video';
}

export function formatBytes(bytes: number) {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.ceil(bytes / 1024)} KB`;
}

export function useMediaAttachments() {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [error, setError] = useState('');
  const current = useRef<Attachment[]>([]);
  useEffect(() => () => current.current.forEach((item) => URL.revokeObjectURL(item.url)), []);

  function add(files: File[]) {
    const next = [...current.current];
    const errors: string[] = [];
    for (const file of files) {
      const kind = file.type.startsWith('image/') ? 'image' : 'video';
      const limit = kind === 'image' ? MEDIA_LIMITS.imageBytes : MEDIA_LIMITS.videoBytes;
      if (!MEDIA_ACCEPT.split(',').includes(file.type)) {
        errors.push(`${file.name}: unsupported format.`);
        continue;
      }
      if (!file.size || file.size > limit) {
        errors.push(`${file.name}: use a non-empty file under ${formatBytes(limit)}.`);
        continue;
      }
      if (
        next.some(
          (item) =>
            item.file.name === file.name &&
            item.file.size === file.size &&
            item.file.lastModified === file.lastModified,
        )
      )
        continue;
      if (
        next.length >= MEDIA_LIMITS.count ||
        next.reduce((sum, item) => sum + item.file.size, 0) + file.size > MEDIA_LIMITS.totalBytes
      ) {
        errors.push('Attach up to 4 files, with a combined size of 100 MB.');
        continue;
      }
      next.push({ id: crypto.randomUUID(), file, kind, url: URL.createObjectURL(file) });
    }
    current.current = next;
    setAttachments(next);
    setError([...new Set(errors)].join(' '));
  }
  function remove(id?: string) {
    const removed = current.current.filter((item) => !id || item.id === id);
    removed.forEach((item) => URL.revokeObjectURL(item.url));
    current.current = current.current.filter((item) => !removed.includes(item));
    setAttachments(current.current);
    setError('');
  }
  return { attachments, error, add, remove };
}
