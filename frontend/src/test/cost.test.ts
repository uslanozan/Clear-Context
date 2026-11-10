import { estimateModelCost, formatCost } from '../lib/cost';
import type { ModelPrices, ModelUsage } from '../lib/types';

const prices: ModelPrices = {
  currency: 'USD',
  checked_on: '2026-11-10',
  per_million_tokens: { 'muse-spark-1.3': { input: 1.25, cached_input: 0.15, output: 4.25 } },
};

function call(input: number | null, output: number | null, cached: number | null = null) {
  return {
    task: 'judge',
    model_id: 'muse-spark-1.3',
    input_tokens: input,
    output_tokens: output,
    cached_input_tokens: cached,
  } satisfies ModelUsage;
}

it('prices input, cached input and output tokens separately', () => {
  const cost = estimateModelCost([call(1_000_000, 100_000, 200_000)], prices);
  // 800k fresh input, 200k cached, 100k output.
  expect(cost).toBeCloseTo(1.0 + 0.03 + 0.425, 6);
});

it('sums every recorded call', () => {
  expect(estimateModelCost([call(40_000, 8_000), call(10_000, 2_000)], prices)).toBeCloseTo(
    0.105,
    6,
  );
});

it('gives no total when a call lacks token counts or a price', () => {
  expect(estimateModelCost([call(1000, null)], prices)).toBeNull();
  expect(
    estimateModelCost([{ ...call(1000, 1000), model_id: 'unknown-model' }], prices),
  ).toBeNull();
});

it('keeps sub-cent amounts visible', () => {
  expect(formatCost(0.11, 'USD')).toBe('$0.11');
  expect(formatCost(0.0042, 'USD')).toBe('$0.0042');
});
