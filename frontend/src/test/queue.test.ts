import { queueMessage } from '../lib/stages';

it('says how many investigations wait ahead, only while queued', () => {
  expect(queueMessage('queued', 2)).toBe('Waiting for 2 earlier investigations to finish.');
  expect(queueMessage('queued', 1)).toBe('Waiting for 1 earlier investigation to finish.');
  expect(queueMessage('queued', 0)).toMatch(/Starting next/);
  expect(queueMessage('running', 3)).toBeNull();
});
