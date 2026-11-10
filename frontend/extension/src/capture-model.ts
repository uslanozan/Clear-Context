/** What the extension captured and how it becomes an investigation request. */

export type CaptureKind = 'text' | 'pasted' | 'link' | 'image' | 'video' | 'area';

/** Captures made of text only: selected, pasted, or a right-clicked link's address. */
export function isTextKind(kind: CaptureKind) {
  return kind === 'text' || kind === 'pasted' || kind === 'link';
}

export interface PendingCapture {
  kind: CaptureKind;
  // Selected or pasted text, or a link's address; empty for image, video and area captures.
  text: string;
  pageUrl: string | null;
  pageTitle: string | null;
  // JPEG data URL of the captured picture, cropped from the visible tab.
  image: string | null;
  // The page's own address of a right-clicked image, for an optional copy of the original file.
  sourceUrl: string | null;
  capturedAt: number;
  // Set when the capture itself failed, so the window can say why instead of staying silent.
  error?: string;
}

export const DEFAULT_SERVER = 'http://clearcontext.localhost';
// Where this codebase serves the app: Docker (compose.yaml, port 80) first, then the desktop
// app (clear_context.desktop, port 8765) and the Vite development server (WEB_PORT 5173).
// The first that answers is used.
export const KNOWN_SERVERS = [
  DEFAULT_SERVER,
  'http://127.0.0.1:8765',
  'http://clearcontext.localhost:5173',
];
export const MAX_TEXT = 20000;

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * The pixel box to cut from a screenshot. The page reports CSS pixels; the screenshot is in
 * device pixels, so the scale comes from the screenshot width over the viewport width (this
 * also covers browser zoom). The box is kept inside the screenshot.
 */
export function cropBox(
  rect: Rect,
  viewportWidth: number,
  imageWidth: number,
  imageHeight: number,
) {
  const scale = imageWidth / viewportWidth;
  const x = Math.max(0, Math.floor(rect.x * scale));
  const y = Math.max(0, Math.floor(rect.y * scale));
  const right = Math.min(imageWidth, Math.ceil((rect.x + rect.width) * scale));
  const bottom = Math.min(imageHeight, Math.ceil((rect.y + rect.height) * scale));
  return { x, y, width: Math.max(0, right - x), height: Math.max(0, bottom - y) };
}

export function dataUrlToBlob(dataUrl: string): Blob {
  const [header, base64] = dataUrl.split(',', 2);
  const type = /data:([^;]+)/.exec(header)?.[1] ?? 'application/octet-stream';
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type });
}
