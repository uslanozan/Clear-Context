import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { theme } from '../../src/theme';
import { PopupApp } from './PopupApp';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('turns pasted text into a capture for review without sending it', async () => {
  const session: Record<string, unknown> = {};
  const createWindow = vi.fn(async () => ({ id: 7 }));
  vi.stubGlobal('chrome', {
    storage: {
      session: {
        get: vi.fn(async (key: string) => (key in session ? { [key]: session[key] } : {})),
        set: vi.fn(async (items: Record<string, unknown>) => Object.assign(session, items)),
      },
      local: { get: vi.fn(async () => ({})), set: vi.fn(async () => undefined) },
      sync: { get: vi.fn(async () => ({})) },
    },
    runtime: { getURL: (path: string) => `chrome-extension://id/${path}` },
    windows: { create: createWindow },
    tabs: { query: vi.fn(async () => []) },
  });
  const fetchMock = vi.fn(async (_url: string) => {
    throw new TypeError('Failed to fetch');
  });
  vi.stubGlobal('fetch', fetchMock);
  vi.spyOn(window, 'close').mockImplementation(() => {});
  render(
    <MantineProvider theme={theme}>
      <PopupApp />
    </MantineProvider>,
  );
  const continueButton = screen.getByRole('button', { name: 'Continue' });
  expect(continueButton).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Paste text or a link'), {
    target: { value: 'https://news.example/storm' },
  });
  fireEvent.click(continueButton);
  await waitFor(() => expect(createWindow).toHaveBeenCalledTimes(1));
  expect(session.pending).toMatchObject({
    kind: 'pasted',
    text: 'https://news.example/storm',
    pageUrl: null,
  });
  // Only health checks reach the network; the investigation starts in the review window.
  expect(fetchMock.mock.calls.every(([url]) => String(url).endsWith('/api/health'))).toBe(true);
});
