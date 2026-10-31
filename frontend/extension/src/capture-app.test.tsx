import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { theme } from '../../src/theme';
import { CaptureApp } from './CaptureApp';
import type { PendingCapture } from './capture-model';

const capture: PendingCapture = {
  kind: 'text',
  text: 'The storm that hit Izmir yesterday blew roofs off houses.',
  pageUrl: 'https://news.example/storm',
  pageTitle: 'Storm news',
  image: null,
  sourceUrl: null,
  capturedAt: 0,
};

function installChrome(pending: PendingCapture | null, sync: Record<string, unknown> = {}) {
  const session: Record<string, unknown> = pending ? { pending } : {};
  const opened: string[] = [];
  vi.stubGlobal('chrome', {
    storage: {
      session: {
        get: vi.fn(async (key: string) => (key in session ? { [key]: session[key] } : {})),
        set: vi.fn(async (items: Record<string, unknown>) => Object.assign(session, items)),
        remove: vi.fn(async (key: string) => delete session[key]),
      },
      sync: {
        get: vi.fn(async (key: string) => (key in sync ? { [key]: sync[key] } : {})),
        set: vi.fn(async (items: Record<string, unknown>) => Object.assign(sync, items)),
        remove: vi.fn(async (key: string) => delete sync[key]),
      },
    },
    tabs: { create: vi.fn(async ({ url }: { url: string }) => opened.push(url)) },
    permissions: { request: vi.fn(async () => true) },
  });
  return { session, opened };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const investigation = {
  id: 'inv-1',
  text: 'x',
  status: 'queued',
  mode: 'meta',
  research_mode: 'fast',
  revision: 1,
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
  error_code: null,
  model_usage: [],
};

function renderApp() {
  render(
    <MantineProvider theme={theme}>
      <CaptureApp />
    </MantineProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('sends the capture only on Investigate, then shows recorded steps and opens the report', async () => {
  const { session, opened } = installChrome(capture);
  const posts: { url: string; body: unknown }[] = [];
  let reads = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) => {
      if (input.endsWith('/health')) {
        return json({
          status: 'ok',
          mode: 'meta',
          research_enabled: true,
          default_research_mode: 'fast',
        });
      }
      if (init?.method === 'POST') {
        posts.push({ url: input, body: JSON.parse(String(init.body)) });
        return json(investigation, 202);
      }
      if (input.endsWith('/steps')) {
        return json([{ id: 1, name: 'graph_started', status: 'completed', created_at: '' }]);
      }
      reads += 1;
      return json({ ...investigation, status: reads > 1 ? 'completed' : 'running' });
    }),
  );
  renderApp();
  expect(await screen.findByText(/Connected/)).toBeInTheDocument();
  expect(posts).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Investigate' }));
  await waitFor(() => expect(posts).toHaveLength(1));
  expect(posts[0].url).toBe('http://clearcontext.localhost/api/investigations');
  expect(posts[0].body).toEqual({
    text: `${capture.text}\n\nhttps://news.example/storm`,
    research_mode: 'fast',
  });
  // The capture is removed once the server accepted it, so it is never sent twice.
  expect(session.pending).toBeUndefined();
  expect(await screen.findByText('Report ready', {}, { timeout: 6000 })).toBeInTheDocument();
  expect(screen.getByText('Receive input')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Open report/ }));
  expect(opened).toEqual(['http://clearcontext.localhost/investigations/inv-1']);
}, 10000);

it('keeps the capture and the edited text when the server refuses the request', async () => {
  const { session } = installChrome(capture);
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, init?: RequestInit) =>
      input.endsWith('/health')
        ? json({ status: 'ok', mode: 'meta', research_enabled: false })
        : init?.method === 'POST'
          ? json({ detail: 'Text must contain 1-20,000 characters.' }, 422)
          : json({}),
    ),
  );
  renderApp();
  const box = await screen.findByLabelText('Text to check');
  fireEvent.change(box, { target: { value: 'Edited claim.' } });
  await screen.findByText(/Connected/);
  fireEvent.click(screen.getByRole('button', { name: 'Investigate' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Text must contain');
  expect(box).toHaveValue('Edited claim.');
  expect(session.pending).toBeDefined();
});

it('says what to do when nothing was captured or the server is down', async () => {
  installChrome(null);
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    }),
  );
  renderApp();
  expect(await screen.findByText('Nothing captured yet')).toBeInTheDocument();
  expect(await screen.findByText(/Not running: start Clear Context/)).toBeInTheDocument();
});

it('finds the development server when Docker is not running', async () => {
  installChrome(capture);
  const probed: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      probed.push(input);
      if (input === 'http://clearcontext.localhost:5173/api/health') {
        return json({ status: 'ok', mode: 'meta', research_enabled: true });
      }
      throw new TypeError('Failed to fetch');
    }),
  );
  renderApp();
  expect(await screen.findByText(/clearcontext.localhost:5173 · Connected/)).toBeInTheDocument();
  expect(probed).toContain('http://clearcontext.localhost/api/health');
});

it('uses an address the user picked without probing the known ones', async () => {
  installChrome(capture, { serverChoice: 'http://192.168.1.5:8080' });
  const probed: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => {
      probed.push(input);
      return json({ status: 'ok', mode: 'meta', research_enabled: true });
    }),
  );
  renderApp();
  expect(await screen.findByText(/192.168.1.5:8080 · Connected/)).toBeInTheDocument();
  expect(probed.every((url) => url.startsWith('http://192.168.1.5:8080'))).toBe(true);
});
