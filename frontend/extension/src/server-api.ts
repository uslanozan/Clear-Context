import type { Health, Investigation, ResearchMode, ResearchStep } from '../../src/lib/types';
import { dataUrlToBlob } from './capture-model';

export class ServerError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(server: string, path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${server}/api${path}`, { ...init, credentials: 'omit' });
  } catch {
    throw new ServerError(0, `Clear Context could not be reached at ${server}.`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ServerError(
      response.status,
      typeof body?.detail === 'string' ? body.detail : 'The request could not be completed.',
    );
  }
  return response.json() as Promise<T>;
}

export const serverApi = {
  health: (server: string, signal?: AbortSignal) => request<Health>(server, '/health', { signal }),
  investigation: (server: string, id: string) =>
    request<Investigation>(server, `/investigations/${encodeURIComponent(id)}`),
  steps: (server: string, id: string) =>
    request<ResearchStep[]>(server, `/investigations/${encodeURIComponent(id)}/steps`),
  /** Start a paid investigation; called only from the Investigate button, never retried. */
  start(server: string, input: { text: string; image: string | null; mode?: ResearchMode }) {
    if (input.image) {
      const form = new FormData();
      form.append('text', input.text);
      if (input.mode) form.append('research_mode', input.mode);
      form.append('files', dataUrlToBlob(input.image), 'capture.jpg');
      return request<Investigation>(server, '/investigations/upload', {
        method: 'POST',
        body: form,
      });
    }
    return request<Investigation>(server, '/investigations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: input.text, research_mode: input.mode }),
    });
  },
};
