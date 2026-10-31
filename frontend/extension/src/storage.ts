import { DEFAULT_SERVER, type PendingCapture } from './capture-model';

// The capture lives only for the browser session; nothing is sent until the user confirms.
const PENDING = 'pending';
const SERVER = 'server';
const WINDOW = 'captureWindow';

export async function savePending(capture: PendingCapture) {
  await chrome.storage.session.set({ [PENDING]: capture });
}

export async function loadPending(): Promise<PendingCapture | null> {
  const stored = await chrome.storage.session.get(PENDING);
  return (stored[PENDING] as PendingCapture | undefined) ?? null;
}

export async function clearPending() {
  await chrome.storage.session.remove(PENDING);
}

export async function loadServer(): Promise<string> {
  const stored = await chrome.storage.sync.get(SERVER);
  return (stored[SERVER] as string | undefined) ?? DEFAULT_SERVER;
}

export async function saveServer(origin: string) {
  await chrome.storage.sync.set({ [SERVER]: origin });
}

/** Open the capture window, or bring the open one forward and show the new capture. */
export async function openCaptureWindow() {
  const stored = await chrome.storage.session.get(WINDOW);
  const existing = stored[WINDOW] as number | undefined;
  if (existing !== undefined) {
    try {
      const [tab] = await chrome.tabs.query({ windowId: existing });
      if (tab?.id !== undefined) {
        await chrome.tabs.reload(tab.id);
        await chrome.windows.update(existing, { focused: true });
        return;
      }
    } catch {
      // The window was closed; open a new one below.
    }
  }
  const created = await chrome.windows.create({
    url: chrome.runtime.getURL('capture.html'),
    type: 'popup',
    width: 460,
    height: 760,
  });
  if (created?.id !== undefined) await chrome.storage.session.set({ [WINDOW]: created.id });
}
