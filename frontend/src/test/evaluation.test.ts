import { describe, expect, it } from 'vitest';
import { readRuns } from '../components/EvaluationView';

function localFile(path: string, content: string): File {
  return {
    name: path.split('/').at(-1),
    webkitRelativePath: path,
    text: async () => content,
  } as File;
}

describe('local evaluation runs', () => {
  it('joins metadata and results by folder and skips malformed runs', async () => {
    const files = [
      localFile(
        'runs/good/run.json',
        JSON.stringify({ configured_model: 'spark', prompt_version: 'v2' }),
      ),
      localFile(
        'runs/good/results.jsonl',
        JSON.stringify({ id: 'case', text: 'A claim', language: 'en' }),
      ),
      localFile('runs/bad/run.json', '{'),
      localFile('runs/bad/results.jsonl', '{}'),
      localFile('runs/other/summary.json', '{}'),
    ];
    const loaded = await readRuns(files);
    expect(loaded.runs).toHaveLength(1);
    expect(loaded.runs[0].model).toBe('spark');
    expect(loaded.runs[0].results[0].text).toBe('A claim');
    expect(loaded.skipped).toBe(1);
  });
});
