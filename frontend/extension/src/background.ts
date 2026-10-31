/**
 * Service worker: context menus, screenshots of the visible tab and cropping.
 *
 * Images are cut from a screenshot of what the user sees, which works on pages that need a
 * login and needs no access to the image's server. The original file can be fetched later from
 * the capture window, after the user grants access to that site.
 */
import { cropBox, type CaptureKind, type Rect } from './capture-model';
import { probePage, type Probe } from './page-probe';
import { openCaptureWindow, savePending } from './storage';

const TEXT_MENU = 'clear-context-text';
const MEDIA_MENU = 'clear-context-media';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: TEXT_MENU,
    title: 'Check with Clear Context',
    contexts: ['selection'],
  });
  chrome.contextMenus.create({
    id: MEDIA_MENU,
    title: 'Check with Clear Context',
    contexts: ['image', 'video'],
  });
});

function toDataUrl(bytes: ArrayBuffer, type: string) {
  let binary = '';
  const view = new Uint8Array(bytes);
  for (let i = 0; i < view.length; i += 0x8000) {
    binary += String.fromCharCode(...view.subarray(i, i + 0x8000));
  }
  return `data:${type};base64,${btoa(binary)}`;
}

/** Screenshot the visible tab and cut out the rectangle, as a JPEG data URL. */
async function captureRect(windowId: number, rect: Rect, viewportWidth: number) {
  const screenshot = await chrome.tabs.captureVisibleTab(windowId, { format: 'png' });
  const bitmap = await createImageBitmap(await (await fetch(screenshot)).blob());
  const box = cropBox(rect, viewportWidth, bitmap.width, bitmap.height);
  if (box.width < 8 || box.height < 8) throw new Error('The selected area is too small.');
  const canvas = new OffscreenCanvas(box.width, box.height);
  canvas
    .getContext('2d')!
    .drawImage(bitmap, box.x, box.y, box.width, box.height, 0, 0, box.width, box.height);
  const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.92 });
  return toDataUrl(await blob.arrayBuffer(), 'image/jpeg');
}

async function savePicture(
  tab: chrome.tabs.Tab,
  kind: CaptureKind,
  image: string,
  sourceUrl: string | null,
  post: string | null = null,
) {
  await savePending({
    kind,
    text: '',
    pageUrl: post ?? tab.url ?? null,
    fromPost: !!post,
    pageTitle: tab.title ?? null,
    image,
    sourceUrl,
    capturedAt: Date.now(),
  });
  await openCaptureWindow();
}

/** Tell the user why a capture failed; the window offers the other ways to capture. */
async function reportFailure(tab: chrome.tabs.Tab, kind: CaptureKind, error: unknown) {
  await savePending({
    kind,
    text: '',
    pageUrl: tab.url ?? null,
    pageTitle: tab.title ?? null,
    image: null,
    sourceUrl: null,
    capturedAt: Date.now(),
    error: error instanceof Error ? error.message : 'The page could not be captured.',
  });
  await openCaptureWindow();
}

/** Look at the page: the right-clicked media (src) or the selection, and their post. */
async function probe(tabId: number, frameId: number | undefined, src: string | null) {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId, frameIds: [frameId ?? 0] },
    func: probePage,
    args: [src],
  });
  return result?.result as Probe | undefined;
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab?.id || tab.windowId === undefined) return;
  if (info.menuItemId === TEXT_MENU) {
    // On a feed the page address is the feed; the selected post has its own link.
    const post = await probe(tab.id, info.frameId, null)
      .then((found) => found?.post ?? null)
      .catch(() => null);
    await savePending({
      kind: 'text',
      text: info.selectionText ?? '',
      pageUrl: post ?? info.pageUrl ?? tab.url ?? null,
      fromPost: !!post,
      pageTitle: tab.title ?? null,
      image: null,
      sourceUrl: null,
      capturedAt: Date.now(),
    });
    await openCaptureWindow();
    return;
  }
  if (info.menuItemId !== MEDIA_MENU || !info.srcUrl) return;
  const kind: CaptureKind = info.mediaType === 'video' ? 'video' : 'image';
  try {
    const located = await probe(tab.id, info.frameId, info.srcUrl);
    if (!located?.rect) {
      // The element could not be found (for example inside a frame); let the user pick it.
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['area.js'] });
      return;
    }
    const image = await captureRect(tab.windowId, located.rect, located.viewportWidth);
    // Video addresses are often temporary blob: URLs that cannot be fetched again.
    const source = kind === 'image' && /^https?:/i.test(info.srcUrl) ? info.srcUrl : null;
    await savePicture(tab, kind, image, source, located.post);
  } catch (error) {
    await reportFailure(tab, kind, error);
  }
});

// The area overlay (area.ts) reports the rectangle after removing itself from the page.
chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.type !== 'clear-context-area' || !sender.tab?.id) return;
  const tab = sender.tab;
  void (async () => {
    try {
      const image = await captureRect(tab.windowId, message.rect, message.viewportWidth);
      await savePicture(tab, 'area', image, null);
    } catch (error) {
      await reportFailure(tab, 'area', error);
    }
  })();
});
