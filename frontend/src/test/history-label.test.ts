import { describe, expect, it } from 'vitest';
import { historyLabel } from '../lib/labels';

describe('historyLabel', () => {
  it('prefers the title the user gave', () => {
    expect(historyLabel({ title: 'Great Wall post', text: 'https://x.com/a/status/1' })).toBe(
      'Great Wall post',
    );
  });

  it('shortens an input that is only a link to its site and first path part', () => {
    expect(historyLabel({ text: 'https://x.com/bulllaw/status/1159220322241044480' })).toBe(
      'x.com/bulllaw',
    );
    expect(historyLabel({ text: '  https://www.bbc.com/  ' })).toBe('bbc.com');
  });

  it('keeps other text as written', () => {
    expect(historyLabel({ text: 'Read this: https://x.com/a/status/1' })).toBe(
      'Read this: https://x.com/a/status/1',
    );
    expect(historyLabel({ text: 'A claim.' })).toBe('A claim.');
  });
});
