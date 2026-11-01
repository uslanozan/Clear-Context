import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../App';
import { theme } from '../theme';

const id = '11111111-1111-4111-8111-111111111111';
const row = {
  id,
  text: 'A synthetic claim.',
  status: 'completed',
  mode: 'meta',
  revision: 1,
  created_at: '2026-10-27T09:00:00Z',
  updated_at: '2026-10-27T09:00:04Z',
  error_code: null,
  model_usage: [],
};
const report = {
  investigation_id: id,
  mode: 'meta',
  revision: 1,
  claims: [{ id: 'claim-1', text: row.text }],
  sources: [],
  evidence: [],
  findings: [
    {
      id: 'finding-1',
      claim_id: 'claim-1',
      assessment: 'unresolved',
      explanation: 'No external evidence was retrieved.',
      evidence_ids: [],
    },
  ],
  limitations: ['Source research is pending.'],
  model_usage: [],
};
let posts: string[];
let bodies: Record<string, unknown>[];
let uploads: { url: string; form: FormData }[];
let researchEnabled: boolean;
let failPost: boolean;
let healthOffline: boolean;
let deletes: string[];

beforeEach(() => {
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:local-test');
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
  posts = [];
  bodies = [];
  uploads = [];
  researchEnabled = false;
  failPost = false;
  healthOffline = false;
  deletes = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string, options?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/health')) {
        if (healthOffline) throw new TypeError('offline');
        return Response.json({
          status: 'ok',
          mode: 'meta',
          paid_api_calls_enabled: true,
          research_enabled: researchEnabled,
        });
      }
      if (options?.method === 'DELETE') {
        deletes.push(url);
        return new Response(null, { status: 204 });
      }
      if (options?.method === 'POST') {
        if (options.body instanceof FormData) {
          uploads.push({ url, form: options.body });
          return Response.json({ ...row, status: 'queued' }, { status: 202 });
        }
        bodies.push(JSON.parse(String(options.body)));
        posts.push(JSON.parse(String(options.body)).text);
        return failPost
          ? Response.json({ detail: 'Service unavailable' }, { status: 503 })
          : Response.json({ ...row, status: 'queued' }, { status: 202 });
      }
      if (url.includes('/report')) return Response.json(report);
      if (url.includes('/steps'))
        return Response.json([
          { name: 'report_saved', status: 'completed', created_at: row.updated_at },
        ]);
      if (url.includes('?limit=')) return Response.json([row]);
      if (url.endsWith(id)) return Response.json(row);
      return Response.json({ detail: 'Not found.' }, { status: 404 });
    }),
  );
});

function mount(path = '/') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <MantineProvider theme={theme}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe('Investigation workspace', () => {
  it('loads the workspace without submitting a paid request', async () => {
    mount();
    await screen.findByRole('textbox', { name: 'Passage to investigate' });
    expect(screen.queryByText('Try a text example')).not.toBeInTheDocument();
    expect(posts).toHaveLength(0);
  });

  it('submits once, opens a report, and labels missing evidence honestly', async () => {
    mount();
    await screen.findByRole('textbox', { name: 'Passage to investigate' });
    fireEvent.change(screen.getByRole('textbox', { name: 'Passage to investigate' }), {
      target: { value: ' A synthetic claim. ' },
    });
    await userEvent.dblClick(screen.getByRole('button', { name: 'Start investigation' }));
    await screen.findByText('Claims extracted; evidence is still missing');
    expect(posts).toEqual(['A synthetic claim.']);
    expect(screen.getByText('Unresolved')).toBeInTheDocument();
    expect(screen.getByText('No evidence attached')).toBeInTheDocument();
  });

  it('sends the chosen research depth only when source research is enabled', async () => {
    researchEnabled = true;
    mount();
    await screen.findByText('Research depth');
    expect(screen.getByText(/Up to 6 searches; every page found is read/)).toBeInTheDocument();
    await userEvent.click(screen.getByText('Deep'));
    expect(screen.getByText(/Uses more credits/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: 'Passage to investigate' }), {
      target: { value: 'A synthetic claim.' },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Start investigation' }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({ text: 'A synthetic claim.', research_mode: 'deep' });
  });

  it('hides research depth when source research is disabled', async () => {
    mount();
    await screen.findByRole('textbox', { name: 'Passage to investigate' });
    expect(screen.queryByText('Research depth')).not.toBeInTheDocument();
  });

  it('preserves the passage and never retries a failed submission automatically', async () => {
    failPost = true;
    mount();
    await screen.findByRole('textbox', { name: 'Passage to investigate' });
    const input = screen.getByRole('textbox', { name: 'Passage to investigate' });
    fireEvent.change(input, { target: { value: 'Keep this passage.' } });
    await userEvent.click(screen.getByRole('button', { name: 'Start investigation' }));
    await screen.findByText(/nothing will be submitted again automatically/i);
    expect(input).toHaveValue('Keep this passage.');
    expect(posts).toEqual(['Keep this passage.']);
  });

  it('opens saved results without another model call', async () => {
    mount(`/investigations/${id}`);
    await screen.findByText('Investigation report');
    expect(posts).toHaveLength(0);
    // The input is always shown, under its own heading.
    expect(screen.getByRole('heading', { name: 'Your input' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Your input/ })).not.toBeInTheDocument();
    expect(screen.getAllByText('A synthetic claim.').length).toBeGreaterThan(0);
  });

  it('deletes an investigation only after confirmation', async () => {
    mount(`/investigations/${id}`);
    await screen.findByText('Investigation report');
    await userEvent.click(screen.getAllByRole('button', { name: 'Investigation actions' })[0]);
    await userEvent.click(await screen.findByRole('menuitem', { name: /Delete/ }));
    expect(await screen.findByText('Delete this investigation?')).toBeInTheDocument();
    expect(deletes).toEqual([]);
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(deletes).toEqual([`/api/investigations/${id}`]));
    // The open report was the deleted one, so the workspace opens instead.
    await screen.findByRole('button', { name: 'Start investigation' });
    expect(posts).toHaveLength(0);
  });

  it('disables paid submission while the backend is disconnected', async () => {
    healthOffline = true;
    mount();
    await screen.findByText('Your investigation service is unavailable');
    fireEvent.change(screen.getByRole('textbox', { name: 'Passage to investigate' }), {
      target: { value: 'A synthetic claim.' },
    });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Start investigation' })).toBeDisabled(),
    );
    expect(posts).toHaveLength(0);
  });
});

describe('Media intake', () => {
  const image = () => new File(['synthetic image bytes'], 'screenshot.png', { type: 'image/png' });
  it('sends a pasted image with its caption to the upload endpoint', async () => {
    mount();
    await screen.findByRole('textbox', { name: 'Passage to investigate' });
    const input = screen.getByRole('textbox', { name: 'Passage to investigate' });
    fireEvent.paste(input, { clipboardData: { files: [image()], getData: () => 'A caption.' } });
    expect(screen.getByAltText('Preview of screenshot.png')).toBeInTheDocument();
    expect(input).toHaveValue('A caption.');
    expect(screen.getByText('Files are sent with your text')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Start investigation' }));
    await waitFor(() => expect(uploads).toHaveLength(1));
    expect(uploads[0].url).toContain('/investigations/upload');
    expect(uploads[0].form.get('text')).toBe('A caption.');
    expect((uploads[0].form.get('files') as File).name).toBe('screenshot.png');
    expect(posts).toHaveLength(0);
  });
  it('allows an image without text but not an empty submission', async () => {
    mount();
    const button = await screen.findByRole('button', { name: 'Start investigation' });
    await waitFor(() => expect(button).toBeDisabled());
    fireEvent.change(screen.getByLabelText('Attach images or videos'), {
      target: { files: [image()] },
    });
    await waitFor(() => expect(button).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: 'Remove screenshot.png' }));
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:local-test');
    expect(button).toBeDisabled();
  });
  it('previews a selected video with playback controls without uploading it', async () => {
    mount();
    const video = new File(['synthetic video bytes'], 'clip.mp4', { type: 'video/mp4' });
    await userEvent.upload(screen.getByLabelText('Attach images or videos'), video);
    expect(screen.getByLabelText('Preview of clip.mp4')).toHaveAttribute('controls');
    expect(posts).toHaveLength(0);
  });
  it('accepts drag/drop and ignores duplicate files', () => {
    mount();
    const input = screen.getByRole('textbox', { name: 'Passage to investigate' });
    const file = image();
    fireEvent.drop(input, { dataTransfer: { files: [file, file], types: ['Files'] } });
    expect(screen.getAllByAltText('Preview of screenshot.png')).toHaveLength(1);
  });
  it('rejects unsupported and oversized media with inline feedback', () => {
    mount();
    const oversized = image();
    Object.defineProperty(oversized, 'size', { value: 21 * 1024 * 1024 });
    const unsupported = new File(['<svg/>'], 'vector.svg', { type: 'image/svg+xml' });
    fireEvent.change(screen.getByLabelText('Attach images or videos'), {
      target: { files: [oversized, unsupported] },
    });
    expect(screen.getByRole('alert')).toHaveTextContent('unsupported format');
    expect(screen.getByRole('alert')).toHaveTextContent('20.0 MB');
    expect(screen.queryByRole('list', { name: 'Attached media' })).not.toBeInTheDocument();
  });
  it('limits attachment count and releases previews when leaving the screen', () => {
    const { unmount } = mount();
    const files = Array.from(
      { length: 5 },
      (_, index) => new File(['x'], `${index}.png`, { type: 'image/png' }),
    );
    fireEvent.change(screen.getByLabelText('Attach images or videos'), { target: { files } });
    expect(screen.getAllByRole('img', { name: /Preview of/ })).toHaveLength(4);
    expect(screen.getByRole('alert')).toHaveTextContent('up to 4 files');
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(4);
  });
});

it('explains an unavailable media preview and preserves its removal control', () => {
  mount();
  fireEvent.change(screen.getByLabelText('Attach images or videos'), {
    target: { files: [new File(['bad'], 'broken.png', { type: 'image/png' })] },
  });
  fireEvent.error(screen.getByAltText('Preview of broken.png'));
  expect(screen.getByText(/This browser cannot preview this file/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Remove broken.png' })).toBeInTheDocument();
});
