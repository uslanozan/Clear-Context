import type { Rect } from './capture-model';

export interface Probe {
  // The right-clicked image or video, inside the viewport; null for a text selection or when
  // the element is not found.
  rect: Rect | null;
  viewportWidth: number;
  // The permanent link of the post around the selection or the media, on feeds such as X,
  // Mastodon or Bluesky; null outside a post.
  post: string | null;
}

/**
 * Runs in the page through chrome.scripting, which sends only this function's source: it must
 * not use anything from outside its own body. Without src it looks at the current selection.
 */
export function probePage(src: string | null): Probe {
  function postLink(element: Element | null): string | null {
    const post = element?.closest('article, [role="article"]');
    if (!post) return null;
    // The link around the timestamp is the post's own address on most feeds.
    const link =
      post.querySelector('a[href] time')?.closest('a') ??
      post.querySelector('a[href*="/status/"], a[href*="/post/"], a[href*="/posts/"]');
    if (!(link instanceof HTMLAnchorElement)) return null;
    try {
      const url = new URL(link.href, location.href);
      return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
    } catch {
      return null;
    }
  }

  const viewportWidth = window.innerWidth;
  if (src === null) {
    const node = window.getSelection()?.anchorNode ?? null;
    const start = node instanceof Element ? node : (node?.parentElement ?? null);
    return { rect: null, viewportWidth, post: postLink(start) };
  }
  const element = Array.from(document.querySelectorAll('img, video')).find((item) => {
    const media = item as HTMLImageElement | HTMLVideoElement;
    return media.currentSrc === src || media.getAttribute('src') === src || media.src === src;
  });
  if (!element) return { rect: null, viewportWidth, post: null };
  const box = element.getBoundingClientRect();
  // Only the part inside the viewport is in a screenshot.
  const x = Math.max(0, box.left);
  const y = Math.max(0, box.top);
  const right = Math.min(window.innerWidth, box.right);
  const bottom = Math.min(window.innerHeight, box.bottom);
  const visible = right - x >= 8 && bottom - y >= 8;
  return {
    rect: visible ? { x, y, width: right - x, height: bottom - y } : null,
    viewportWidth,
    post: postLink(element),
  };
}
