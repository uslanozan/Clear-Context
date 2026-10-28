import { useRef, useState } from 'react';
import { Alert, Button } from '@mantine/core';
import { FolderOpen, RefreshCw } from 'lucide-react';
import { ClaimSource } from './ClaimSource';
import type { ExtractedClaim } from '../lib/types';

type Chunk = { start: number; end: number; status: string; reason: string | null };
type Usage = {
  input_tokens: number | null;
  output_tokens: number | null;
  cached_input_tokens: number | null;
};
type Result = {
  id: string;
  language: string;
  text: string;
  status: string;
  elapsed_seconds: number;
  attempted_model_calls: number;
  extraction?: {
    claims: ExtractedClaim[];
    coverage: { status: string; model_calls: number; chunks: Chunk[] };
    model_usage: Usage[];
  };
  error_code?: string;
};
type Run = {
  id: string;
  model: string;
  prompt: string;
  started: string;
  prices: { input: number; cached_input: number; output: number } | null;
  results: Result[];
};

export async function readRuns(files: File[]): Promise<{ runs: Run[]; skipped: number }> {
  const folders = new Map<string, Map<string, File>>();
  for (const file of files) {
    const parts = file.webkitRelativePath.split('/');
    if (parts.length < 3 || !['run.json', 'results.jsonl'].includes(file.name)) continue;
    const folder = parts.slice(0, -1).join('/');
    const group = folders.get(folder) || new Map<string, File>();
    group.set(file.name, file);
    folders.set(folder, group);
  }
  const runs: Run[] = [];
  let skipped = 0;
  for (const [folder, group] of folders) {
    const metaFile = group.get('run.json');
    const resultFile = group.get('results.jsonl');
    if (!metaFile || !resultFile) continue;
    try {
      const meta = JSON.parse(await metaFile.text());
      const results = (await resultFile.text())
        .split(/\r?\n/)
        .filter(Boolean)
        .map((line) => JSON.parse(line) as Result);
      if (
        typeof meta.configured_model !== 'string' ||
        !results.every((r: Result) => typeof r.id === 'string' && typeof r.text === 'string')
      )
        throw new Error('Invalid run');
      runs.push({
        id: folder.split('/').at(-1)!,
        model: meta.configured_model,
        prompt: meta.prompt_version || 'unknown',
        started: meta.started_at || '',
        prices: meta.price_snapshot || null,
        results,
      });
    } catch {
      skipped += 1;
    }
  }
  runs.sort((a, b) => b.started.localeCompare(a.started));
  return { runs, skipped };
}

const caseNames: Record<string, string> = {
  'cc-v1-507ae9c8e914': 'Marie Curie · modified',
  'cc-v1-ba672c905381': 'Mars moons · uncertain',
  'cc-v1-f94cc987d232': 'Cappadocia · original',
};

function estimate(run: Run, result: Result): string {
  const usage = result.extraction?.model_usage;
  if (
    !run.prices ||
    !usage?.length ||
    usage.length < result.attempted_model_calls ||
    usage.some(
      (u) => u.input_tokens == null || u.output_tokens == null || u.cached_input_tokens == null,
    )
  )
    return 'Unavailable';
  const total = usage.reduce(
    (sum, u) =>
      sum +
      ((u.input_tokens! - u.cached_input_tokens!) * run.prices!.input +
        u.cached_input_tokens! * run.prices!.cached_input +
        u.output_tokens! * run.prices!.output) /
        1_000_000,
    0,
  );
  return `~$${total.toFixed(4)}`;
}

export function EvaluationView() {
  const picker = useRef<HTMLInputElement>(null);
  const passage = useRef<HTMLDivElement>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [caseId, setCaseId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeSpan, setActiveSpan] = useState<{ start: number; end: number } | null>(null);
  const chosen = selected
    .map((id) => runs.find((run) => run.id === id))
    .filter((run): run is Run => Boolean(run));
  const cases = Array.from(
    new Map(
      chosen.flatMap((run) => run.results.map((result) => [result.id, result] as const)),
    ).values(),
  );
  const current = cases.find((item) => item.id === caseId) || cases[0];
  const matching = chosen.map((run) => ({
    run,
    result: run.results.find((item) => item.id === current?.id),
  }));
  const mismatch = matching.some(({ result }) => result && result.text !== current?.text);

  async function load(files: File[]) {
    setLoading(true);
    setError('');
    try {
      const loaded = await readRuns(files);
      if (!loaded.runs.length) {
        setError(
          'No complete run folders found. Select the evals/runs folder containing run.json and results.jsonl.',
        );
        return;
      }
      const preferred = loaded.runs.filter((r) => r.prompt === 'v2');
      const first = preferred[0] || loaded.runs[0];
      const second = preferred.find(
        (r) =>
          r.model !== first.model &&
          r.results.some((row) =>
            first.results.some((other) => other.id === row.id && other.text === row.text),
          ),
      );
      setRuns(loaded.runs);
      setSelected([first.id, ...(second ? [second.id] : [])]);
      setCaseId(first.results[0]?.id || '');
      setActiveSpan(null);
      if (loaded.skipped) setError(`${loaded.skipped} malformed run folder(s) could not be read.`);
    } catch {
      setError('The selected files could not be read. Try selecting the runs folder again.');
    } finally {
      setLoading(false);
      if (picker.current) picker.current.value = '';
    }
  }
  function highlight(span: { start: number; end: number }) {
    setActiveSpan(span);
    requestAnimationFrame(() =>
      passage.current?.querySelector('mark')?.scrollIntoView({ block: 'center' }),
    );
  }
  function changeRun(index: number, id: string) {
    setSelected((old) => {
      const next = [...old];
      next[index] = id;
      return next;
    });
    setCaseId('');
    setActiveSpan(null);
  }
  const chars = Array.from(current?.text || '');
  const validSpan =
    activeSpan &&
    activeSpan.start >= 0 &&
    activeSpan.end <= chars.length &&
    activeSpan.end > activeSpan.start;
  return (
    <div className="evaluation-page">
      <div className="evaluation-heading">
        <div>
          <h1>Extraction review</h1>
          <p>Inspect saved model runs, their source passages, and processing gaps.</p>
        </div>
        <Button
          variant="default"
          leftSection={<FolderOpen size={16} />}
          loading={loading}
          onClick={() => picker.current?.click()}
        >
          {runs.length ? 'Choose folder again' : 'Open runs folder'}
        </Button>
        <input
          ref={(node) => {
            picker.current = node;
            if (node) node.setAttribute('webkitdirectory', '');
          }}
          type="file"
          multiple
          hidden
          onChange={(event) => void load(Array.from(event.currentTarget.files || []))}
        />
      </div>
      <p className="evaluation-notice">
        Read-only review · Files stay in your browser · No model calls
      </p>
      {error && (
        <Alert color="orange" title="Some results are unavailable">
          {error}
        </Alert>
      )}
      {!runs.length ? (
        <div className="evaluation-empty">
          <FolderOpen size={28} strokeWidth={1.4} />
          <h2>Open your saved runs</h2>
          <p>
            Choose the project’s <code>evals/runs</code> folder. The browser reads its saved run
            metadata and results locally; no files are uploaded.
          </p>
          <p>The folder is local and ignored by Git, so it may be empty on another installation.</p>
        </div>
      ) : (
        <>
          <div className="evaluation-controls">
            {[0, 1].map((index) => (
              <label key={index}>
                Model run {index + 1}
                <select
                  value={selected[index] || ''}
                  onChange={(event) => changeRun(index, event.target.value)}
                >
                  <option value="">No run selected</option>
                  {runs.map((run) => (
                    <option value={run.id} key={run.id}>
                      {run.model} · {run.prompt} · {run.id}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <label>
              Input
              <select
                value={current?.id || ''}
                onChange={(event) => {
                  setCaseId(event.target.value);
                  setActiveSpan(null);
                }}
              >
                {cases.map((item) => (
                  <option value={item.id} key={item.id}>
                    {caseNames[item.id] || item.id} · {item.language}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {mismatch && (
            <Alert color="orange" title="Inputs differ">
              These runs used different text for the same ID. Compare the source passages
              separately.
            </Alert>
          )}
          {current && (
            <section className="evaluation-input">
              <div className="evaluation-section-heading">
                <div>
                  <h2>Original passage</h2>
                  <p>
                    {current.id} · {current.language} · {chars.length.toLocaleString()} characters
                  </p>
                </div>
                {activeSpan && (
                  <button className="text-button" onClick={() => setActiveSpan(null)}>
                    <RefreshCw size={13} /> Clear highlight
                  </button>
                )}
              </div>
              <div ref={passage} className="evaluation-passage" dir="auto">
                {validSpan ? (
                  <>
                    {chars.slice(0, activeSpan!.start).join('')}
                    <mark>{chars.slice(activeSpan!.start, activeSpan!.end).join('')}</mark>
                    {chars.slice(activeSpan!.end).join('')}
                  </>
                ) : (
                  current.text
                )}
              </div>
            </section>
          )}
          <p className="evaluation-caveat">
            Processed means the recorded ranges passed structural checks, not that every claim was
            extracted or verified. More claims do not necessarily mean a better result.
          </p>
          <div className="evaluation-comparison">
            {matching.map(({ run, result }) => (
              <section className="evaluation-run" key={run.id}>
                <div className="evaluation-run-heading">
                  <div>
                    <h2>{run.model}</h2>
                    <p>
                      {run.id} · prompt {run.prompt}
                    </p>
                  </div>
                  <span
                    className={`evaluation-status ${result?.extraction?.coverage.status === 'partial' ? 'partial' : ''}`}
                  >
                    {result?.extraction?.coverage.status || result?.status || 'No result'}
                  </span>
                </div>
                {!result ? (
                  <p className="muted">This run does not contain the selected input.</p>
                ) : (
                  <>
                    <div className="evaluation-stats">
                      <span>
                        <strong>{result.extraction?.claims.length ?? 0}</strong> claims
                      </span>
                      <span>
                        <strong>{result.attempted_model_calls}</strong> calls
                      </span>
                      <span>
                        <strong>{result.elapsed_seconds?.toFixed(1) ?? '—'}s</strong> elapsed
                      </span>
                      <span>
                        <strong>{estimate(run, result)}</strong> estimated
                      </span>
                    </div>
                    <p className="evaluation-cost-note">
                      Recorded tokens:{' '}
                      {result.extraction?.model_usage
                        .reduce((sum, usage) => sum + (usage.input_tokens || 0), 0)
                        .toLocaleString() ?? 'unavailable'}{' '}
                      input /{' '}
                      {result.extraction?.model_usage
                        .reduce((sum, usage) => sum + (usage.output_tokens || 0), 0)
                        .toLocaleString() ?? 'unavailable'}{' '}
                      output. Missing receipts may make totals incomplete.
                      <br />
                      Estimate uses recorded tokens and the run’s price snapshot; billing may
                      differ.
                    </p>
                    {result.error_code && <Alert color="orange">{result.error_code}</Alert>}
                    {result.extraction && (
                      <>
                        <details
                          className="evaluation-chunks"
                          open={result.extraction.coverage.status === 'partial'}
                        >
                          <summary>
                            Processing ranges ({result.extraction.coverage.chunks.length})
                          </summary>
                          <div>
                            {result.extraction.coverage.chunks.map((chunk, index) => (
                              <button
                                key={`${chunk.start}-${index}`}
                                onClick={() => {
                                  if (!mismatch) highlight(chunk);
                                }}
                                disabled={mismatch}
                              >
                                <span>
                                  {chunk.start}–{chunk.end}
                                </span>
                                <span>
                                  {chunk.status}
                                  {chunk.reason ? ` · ${chunk.reason}` : ''}
                                </span>
                              </button>
                            ))}
                          </div>
                        </details>
                        <h3>Extracted claims</h3>
                        <div className="evaluation-claims">
                          {result.extraction.claims.map((claim, index) => (
                            <article key={claim.id || index}>
                              <div className="evaluation-claim-number">{index + 1}</div>
                              <div>
                                <p dir="auto">{claim.statement || claim.text}</p>
                                <ClaimSource claim={claim} input={result.text} />
                                {claim.source_span && !mismatch && (
                                  <button
                                    className="text-button"
                                    onClick={() => highlight(claim.source_span!)}
                                  >
                                    Highlight in original
                                  </button>
                                )}
                              </div>
                            </article>
                          ))}
                          {!result.extraction.claims.length && (
                            <p className="muted">No claims were recorded for this input.</p>
                          )}
                        </div>
                      </>
                    )}
                  </>
                )}
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
