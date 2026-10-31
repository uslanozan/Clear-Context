import { useEffect, useState } from 'react';
import { Alert, Button, Textarea } from '@mantine/core';
import { ArrowUpRight, Crop, TextSelect } from 'lucide-react';
import { MAX_TEXT } from './capture-model';
import { ServerLine, useServer } from './ServerLine';
import { loadPending, openCaptureWindow, savePending } from './storage';

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
  const [hasPending, setHasPending] = useState(false);
  const [error, setError] = useState('');
  const [pasted, setPasted] = useState('');
  const { server: found, connection, choose } = useServer();
  const server = found?.origin ?? null;

  useEffect(() => {
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

  async function usePasted() {
    await savePending({
      kind: 'pasted',
      text: pasted,
      pageUrl: null,
      pageTitle: null,
      image: null,
      sourceUrl: null,
      capturedAt: Date.now(),
    });
    await openCaptureWindow();
    window.close();
  }

  return (
    <main className="ext-popup">
      <header className="ext-header">
        <span className="brand-icon" aria-hidden="true">
          <img src="icons/icon-32.png" alt="" width={20} height={20} />
        </span>
        <div>
          <strong>Clear Context</strong>
          {found && (
            <ServerLine
              server={found.origin}
              chosen={found.chosen}
              connection={connection}
              onChoose={(origin) => void choose(origin)}
            />
          )}
        </div>
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
      <form
        className="ext-paste"
        onSubmit={(event) => {
          event.preventDefault();
          if (pasted.trim()) void usePasted();
        }}
      >
        <Textarea
          label="Paste text or a link"
          description="For example a post's address copied from the address bar."
          autosize
          minRows={2}
          maxRows={5}
          maxLength={MAX_TEXT}
          value={pasted}
          onChange={(event) => setPasted(event.currentTarget.value)}
        />
        <Button type="submit" fullWidth variant="default" disabled={!pasted.trim()}>
          Continue
        </Button>
      </form>
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
      <p className="muted small">Or right-click selected text, a link, an image or a video.</p>
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
