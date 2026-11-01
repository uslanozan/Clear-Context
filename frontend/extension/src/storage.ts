import type { PendingCapture } from './capture-model';

// The capture lives only for the browser session; nothing is sent until the user confirms.
const PENDING = 'pending';
// The last address that answered, tried first next time; never typed in by the user.
const LAST_SERVER = 'lastServer';
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

export async function loadLastServer(): Promise<string | null> {
  try {
    const stored = await chrome.storage.local.get(LAST_SERVER);
    return (stored[LAST_SERVER] as string | undefined) ?? null;
  } catch {
    return null;
  }
}

export async function saveLastServer(origin: string) {
  try {
    await chrome.storage.local.set({ [LAST_SERVER]: origin });
  } catch {
    // Detection simply starts from the known addresses next time.
  }
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
