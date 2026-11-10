import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { SettingsPage } from '../components/SettingsPage';
import type { AppSettings } from '../lib/types';
import { theme } from '../theme';

const settings: AppSettings = {
  keys: {
    meta_api_key: { configured: true, preview: 'LLM_2896...a1b2', source: 'env' },
    tavily_api_key: { configured: true, preview: 'tvly-dev...c3d4', source: 'panel' },
    serp_api_key: { configured: false, preview: null, source: null },
    google_fact_check_api_key: { configured: false, preview: null, source: null },
  },
  paid_calls: false,
  models: {
    claim_extraction: 'spark_1_3',
    screenshot: 'spark_1_3',
    research: 'spark_1_3',
    judge: 'spark_1_3',
  },
  model_options: [
    { alias: 'spark_1_3', name: 'Muse Spark 1.3' },
    { alias: 'wonder', name: 'Muse Wonder' },
  ],
  default_research_mode: 'balanced',
  reverse_image_search: true,
  fact_check_search: true,
  link_reading: true,
  search_min_score: 0.3,
  changed: ['tavily_api_key'],
  error: null,
};
let puts: Record<string, unknown>[];
let failPut: boolean;

beforeEach(() => {
  puts = [];
  failPut = false;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_input: string, options?: RequestInit) => {
      if (options?.method === 'PUT') {
        const body = JSON.parse(String(options.body));
        puts.push(body);
        if (failPut) {
          return new Response(JSON.stringify({ detail: 'Unknown model alias for judge.' }), {
            status: 422,
          });
        }
        return new Response(JSON.stringify({ ...settings, paid_calls: Boolean(body.paid_calls) }));
      }
      return new Response(JSON.stringify(settings));
    }),
  );
});

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MantineProvider theme={theme}>
        <SettingsPage />
      </MantineProvider>
    </QueryClientProvider>,
  );
}

it('shows key status without values and saves only changed fields', async () => {
  renderPage();
  // The saved key shows masked inside its own field, never in full.
  expect(await screen.findByPlaceholderText('LLM_2896...a1b2')).toBeInTheDocument();
  expect(screen.getByPlaceholderText('tvly-dev...c3d4')).toBeInTheDocument();
  const save = screen.getByRole('button', { name: 'Save changes' });
  expect(save).toBeDisabled();
  fireEvent.change(screen.getByLabelText('SerpApi key'), {
    target: { value: '  serp-new-key-123  ' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Use .env value' }));
  fireEvent.click(save);
  await waitFor(() => expect(puts).toHaveLength(1));
  expect(puts[0]).toEqual({ serp_api_key: 'serp-new-key-123', tavily_api_key: null });
  expect(await screen.findByText(/Saved\. The next investigation/)).toBeInTheDocument();
});

it('links each key to the page where it is created', async () => {
  renderPage();
  const links = await screen.findAllByRole('link', { name: 'Get a key' });
  expect(links.map((link) => link.getAttribute('href'))).toEqual([
    'https://dev.meta.ai/',
    'https://app.tavily.com/',
    'https://serpapi.com/manage-api-key',
    'https://console.cloud.google.com/apis/library/factchecktools.googleapis.com',
  ]);
  for (const link of links) expect(link).toHaveAttribute('rel', 'noopener noreferrer');
});

it('keeps entries when saving fails', async () => {
  failPut = true;
  renderPage();
  const input = await screen.findByLabelText('Tavily API key');
  fireEvent.change(input, { target: { value: 'tvly-typed-key-0001' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  expect(await screen.findByText(/Unknown model alias for judge\./)).toBeInTheDocument();
  expect(input).toHaveValue('tvly-typed-key-0001');
});

it('asks before allowing paid calls', async () => {
  renderPage();
  fireEvent.click(await screen.findByRole('switch', { name: 'Allow paid calls' }));
  expect(puts).toHaveLength(0);
  fireEvent.click(await screen.findByRole('button', { name: 'Allow paid calls' }));
  await waitFor(() => expect(puts).toEqual([{ paid_calls: true }]));
});

it('marks values that differ from .env and resets everything after confirmation', async () => {
  settings.changed = ['tavily_api_key', 'model_judge'];
  renderPage();
  expect(await screen.findAllByText('Saved here · differs from .env')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Reset all to .env' }));
  expect(puts).toHaveLength(0);
  fireEvent.click(await screen.findByRole('button', { name: 'Reset all' }));
  await waitFor(() => expect(puts).toHaveLength(1));
  expect(puts[0]).toMatchObject({
    meta_api_key: null,
    model_judge: null,
    paid_calls: null,
    search_min_score: null,
  });
  expect(Object.keys(puts[0])).toHaveLength(14);
  settings.changed = ['tavily_api_key'];
});
