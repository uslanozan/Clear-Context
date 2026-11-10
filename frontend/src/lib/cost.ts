import type { ModelPrices, ModelUsage } from './types';

/**
 * Estimated model cost of recorded calls at catalog list prices, in the catalog currency.
 * Returns null when any call lacks token counts or its model has no token price, so a
 * partial sum is never shown as the total. Search services and transcription are not included.
 */
export function estimateModelCost(usage: ModelUsage[], prices: ModelPrices): number | null {
  let total = 0;
  for (const call of usage) {
    const price = prices.per_million_tokens[call.model_id];
    if (!price || call.input_tokens === null || call.output_tokens === null) return null;
    const cached = Math.min(call.cached_input_tokens ?? 0, call.input_tokens);
    const cachedRate = price.cached_input ?? price.input;
    total +=
      ((call.input_tokens - cached) * price.input +
        cached * cachedRate +
        call.output_tokens * price.output) /
      1_000_000;
  }
  return total;
}

export function formatCost(amount: number, currency: string): string {
  // Below one cent, two decimals would read as free.
  const digits = amount > 0 && amount < 0.01 ? 4 : 2;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount);
}
