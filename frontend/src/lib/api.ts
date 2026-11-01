import type {
  AppSettings,
  Health,
  ResearchOverview,
  HistoryGroup,
  Investigation,
  Report,
  ResearchMode,
  ResearchStep,
  SettingsUpdate,
} from './types';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(
      0,
      'The investigation service could not be reached. Your text has been kept.',
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message =
      typeof body?.detail === 'string' ? body.detail : 'The request could not be completed.';
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>('/health', { signal }),
  history: (offset = 0, signal?: AbortSignal) =>
    request<Investigation[]>(`/investigations?limit=20&offset=${offset}`, { signal }),
  investigation: (id: string, signal?: AbortSignal) =>
    request<Investigation>(`/investigations/${encodeURIComponent(id)}`, { signal }),
  steps: (id: string, signal?: AbortSignal) =>
    request<ResearchStep[]>(`/investigations/${encodeURIComponent(id)}/steps`, { signal }),
  research: (id: string, signal?: AbortSignal) =>
    request<ResearchOverview>(`/investigations/${encodeURIComponent(id)}/research`, { signal }),
  report: (id: string, signal?: AbortSignal) =>
    request<Report>(`/investigations/${encodeURIComponent(id)}/report`, { signal }),
  create: (input: { text: string; research_mode?: ResearchMode }) =>
    request<Investigation>('/investigations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  // Paid follow-up runs; called only from an explicit button press.
  rerun: (id: string, research_mode: ResearchMode) =>
    request<Investigation>(`/investigations/${encodeURIComponent(id)}/rerun`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ research_mode }),
    }),
  continueResearch: (id: string, research_mode: ResearchMode) =>
    request<Investigation>(`/investigations/${encodeURIComponent(id)}/continue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ research_mode }),
    }),
  groups: (signal?: AbortSignal) => request<HistoryGroup[]>('/groups', { signal }),
  createGroup: (name: string) =>
    request<HistoryGroup>('/groups', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  renameGroup: (id: string, name: string) =>
    request<HistoryGroup>(`/groups/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  deleteGroup: (id: string) => request<void>(`/groups/${id}`, { method: 'DELETE' }),
  assignGroup: (id: string, groupId: string | null) =>
    request<void>(`/investigations/${id}/group`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group_id: groupId }),
    }),
  settings: (signal?: AbortSignal) => request<AppSettings>('/settings', { signal }),
  saveSettings: (changes: SettingsUpdate) =>
    request<AppSettings>('/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    }),
  // Multipart: the browser sets the boundary, so no Content-Type header here.
  upload: (input: { text: string; research_mode?: ResearchMode; files: File[] }) => {
    const form = new FormData();
    form.append('text', input.text);
    if (input.research_mode) form.append('research_mode', input.research_mode);
    input.files.forEach((file) => form.append('files', file, file.name));
    return request<Investigation>('/investigations/upload', { method: 'POST', body: form });
  },
};

export function failureMessage(code: string | null) {
  const messages: Record<string, string> = {
    meta_authentication_failed:
      'Meta could not authenticate this request. Check the API key on your server.',
    meta_access_denied: 'Your Meta account does not have access to this model.',
    meta_rate_limited:
      'Meta has reached its request limit. Wait a moment before starting another investigation.',
    meta_timeout: 'Meta took too long to respond. This attempt was stopped.',
    meta_connection_failed: 'The server could not connect to Meta.',
    meta_incomplete_output:
      'The model reached its output limit before finishing. No incomplete result was saved.',
    meta_refused: 'The model declined to process this input.',
    meta_ungrounded_claim:
      'The model introduced wording outside your passage, so the result was rejected.',
    meta_invalid_response: 'The model returned a result that did not pass validation.',
    interrupted: 'The server restarted before this investigation finished.',
  };
  return (
    messages[code || ''] ||
    'This investigation could not be completed. Your original passage is still available.'
  );
}
