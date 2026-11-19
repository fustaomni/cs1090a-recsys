// site/src/mechanisms/lib/moepipeline.test.js
// A.359: the experts and the fitted mixture end to end on the three time windows.
import { describe, expect, it } from 'vitest';
import { arrivingRatings, threeWindows } from './moefit.js';
import { EXPERT_NAMES, fitExperts, reweigh, runMixture } from './moepipeline.js';

const WINDOWS = { validateFrom: 600, testFrom: 800 };

describe('fitExperts', () => {
  it('gives four predictions per rating, each on the five-point scale', () => {
    const { train, validate } = threeWindows(arrivingRatings({ seed: 191 }), WINDOWS);
    const predicted = fitExperts(train).predict(validate);
    expect(EXPERT_NAMES).toHaveLength(4);
    expect(predicted).toHaveLength(validate.length);
    for (const row of predicted) {
      expect(row).toHaveLength(4);
      for (const value of row) {
        expect(value).toBeGreaterThanOrEqual(1);
        expect(value).toBeLessThanOrEqual(5);
      }
    }
  });
  it('falls back to the shared bias for a user and a movie the history never saw', () => {
    const history = [
      { user: 1, movie: 1, time: 1, rating: 4 },
      { user: 2, movie: 2, time: 2, rating: 2 },
    ];
    const [[bias, movieMean, linear]] = fitExperts(history).predict([
      { user: 9, movie: 9, time: 3, rating: 3 },
    ]);
    expect(bias).toBe(3);
    expect(movieMean).toBe(bias);
    expect(linear).toBe(bias);
  });
  it('refuses a rating its history already reaches', () => {
    const history = [{ user: 1, movie: 1, time: 5, rating: 4 }];
    expect(() => fitExperts(history).predict([{ user: 1, movie: 1, time: 5, rating: 3 }]))
      .toThrow(/leakage/);
  });
});

describe('runMixture', () => {
  // Fitted once and shared; built inside each test, so a missing runMixture fails each one.
  let cached;
  const fitted = () => (cached ??= runMixture({ seed: 191 }));
  it('fits its gate on validate, where it beats the uniform mix of the same experts', () => {
    expect(fitted().losses.at(-1)).toBeLessThan(fitted().losses[0]);
    expect(fitted().validation.mixture).toBeLessThan(fitted().validation.uniform);
  });
  it('scores every cold-start bucket of the test window', () => {
    const counts = {};
    for (const row of fitted().rows) counts[row.bucket] = (counts[row.bucket] ?? 0) + 1;
    for (const name of ['warm', 'new user', 'new movie', 'both new']) {
      expect(counts[name], name).toBeGreaterThanOrEqual(30);
    }
  });
  it('reports a weight per expert that sums to one on average', () => {
    expect(fitted().utilisation).toHaveLength(4);
    expect(fitted().utilisation.reduce((sum, value) => sum + value, 0)).toBeCloseTo(1, 12);
  });
  it('sharpens the fitted gate as its temperature falls', () => {
    const sharp = reweigh(fitted(), { temperature: 0.1 });
    const largest = (rows) => rows.reduce((sum, row) => sum + Math.max(...row.weights), 0);
    expect(largest(sharp.rows)).toBeGreaterThan(largest(fitted().rows));
  });
  it('keeps only the top two experts when k is two', () => {
    const sparse = reweigh(fitted(), { k: 2 });
    for (const row of sparse.rows) expect(row.weights.filter((w) => w > 0).length).toBe(2);
  });
  it('is the same run for the same seed', () => {
    expect(runMixture({ seed: 191 }).tested).toEqual(fitted().tested);
  });
});
