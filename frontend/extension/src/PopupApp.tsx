import { useEffect, useState } from 'react';
import { Alert, Button } from '@mantine/core';
import { ArrowUpRight, Crop, TextSelect } from 'lucide-react';
import { loadPending, loadServer, openCaptureWindow, savePending } from './storage';

/** Selected text of the page; runs in the page. */
function readSelection() {
  return {
    text: window.getSelection()?.toString() ?? '',
    url: location.href,
    title: document.title,
  };
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

/** Toolbar popup: start a capture in the current tab or open the last one. */
export function PopupApp() {
  const [server, setServer] = useState<string | null>(null);
  const [hasPending, setHasPending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    void loadServer().then(setServer);
    void loadPending().then((pending) => setHasPending(!!pending));
  }, []);

  async function captureArea() {
    try {
      const tab = await activeTab();
      await chrome.scripting.executeScript({ target: { tabId: tab.id! }, files: ['area.js'] });
      window.close();
    } catch {
      setError("This page can't be captured. Try a regular web page.");
    }
  }

  async function useSelection() {
    try {
      const tab = await activeTab();
      const [result] = await chrome.scripting.executeScript({
        target: { tabId: tab.id! },
        func: readSelection,
      });
      const selection = result?.result as ReturnType<typeof readSelection> | undefined;
      if (!selection?.text.trim()) {
        setError('Select some text on the page first.');
        return;
      }
      await savePending({
        kind: 'text',
        text: selection.text,
        pageUrl: selection.url,
        pageTitle: selection.title,
        image: null,
        sourceUrl: null,
        capturedAt: Date.now(),
      });
      await openCaptureWindow();
      window.close();
    } catch {
      setError("This page can't be read. Try a regular web page.");
    }
  }

  return (
    <main className="ext-popup">
      <header className="ext-header">
        <span className="brand-icon" aria-hidden="true">
          <img src="icons/icon-32.png" alt="" width={20} height={20} />
        </span>
        <strong>Clear Context</strong>
      </header>
      <Button fullWidth leftSection={<Crop size={16} />} onClick={() => void captureArea()}>
        Capture an area
      </Button>
      <Button
        fullWidth
        variant="default"
        leftSection={<TextSelect size={16} />}
        onClick={() => void useSelection()}
      >
        Use selected text
      </Button>
      {hasPending && (
        <Button fullWidth variant="subtle" onClick={() => void openCaptureWindow()}>
          Review the last capture
        </Button>
      )}
      {error && (
        <Alert color="orange" role="alert">
          {error}
        </Alert>
      )}
      <p className="muted small">Or right-click selected text, an image or a video.</p>
      {server && (
        <button
          type="button"
          className="text-button ext-open"
          onClick={() => void chrome.tabs.create({ url: server })}
        >
          Open Clear Context <ArrowUpRight size={13} />
        </button>
      )}
    </main>
  );
}
