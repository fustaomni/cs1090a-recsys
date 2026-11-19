// site/src/mechanisms/lib/moefit.test.js
// A.359: the MoE labs on one three-window time split, with a fitted gate (2026 practice).
import { describe, expect, it } from 'vitest';
import { softmax } from './moe.js';
import {
  arrivingRatings, fitGate, mixturePredict, softmaxT, threeWindows, topK,
  utilisation, windowFeatures,
} from './moefit.js';

const WINDOWS = { validateFrom: 600, testFrom: 800 };
const bucket = ({ userCount, movieCount }) =>
  userCount > 0 ? (movieCount > 0 ? 'warm' : 'new movie')
    : (movieCount > 0 ? 'new user' : 'both new');

describe('arrivingRatings', () => {
  it('fills every cold-start bucket of the test window with at least 30 ratings', () => {
    const { train, validate, test } = threeWindows(arrivingRatings({ seed: 191 }), WINDOWS);
    const counts = { warm: 0, 'new user': 0, 'new movie': 0, 'both new': 0 };
    for (const f of windowFeatures([...train, ...validate], test)) counts[bucket(f)] += 1;
    for (const [name, n] of Object.entries(counts)) expect(n, name).toBeGreaterThanOrEqual(30);
  });
  it('is the same ratings for the same seed', () => {
    expect(arrivingRatings({ seed: 7 })).toEqual(arrivingRatings({ seed: 7 }));
  });
});

describe('threeWindows', () => {
  it('cuts three non-empty windows in time order and keeps every rating', () => {
    const rows = arrivingRatings({ seed: 3 });
    const { train, validate, test } = threeWindows(rows, WINDOWS);
    expect(train.length + validate.length + test.length).toBe(rows.length);
    for (const w of [train, validate, test]) expect(w.length).toBeGreaterThan(0);
    for (const r of train) expect(r.time).toBeLessThan(600);
    for (const r of validate) {
      expect(r.time).toBeGreaterThanOrEqual(600);
      expect(r.time).toBeLessThan(800);
    }
    for (const r of test) expect(r.time).toBeGreaterThanOrEqual(800);
  });
  it('refuses a validation window that does not end before the test window', () => {
    expect(() => threeWindows([], { validateFrom: 800, testFrom: 800 })).toThrow(/window/);
  });
});

describe('windowFeatures', () => {
  it('refuses history that reaches into the rows it describes', () => {
    const { train, validate } = threeWindows(arrivingRatings({ seed: 3 }), WINDOWS);
    expect(() => windowFeatures([...train, ...validate], validate)).toThrow(/leakage/);
  });
});

describe('softmaxT and topK', () => {
  it('is the softmax at temperature 1, sharp when cold and flat when hot', () => {
    const s = [2, 1, 0];
    softmaxT(s, 1).forEach((w, i) => expect(w).toBeCloseTo(softmax(s)[i], 12));
    expect(softmaxT(s, 0.05)[0]).toBeGreaterThan(0.999);
    for (const w of softmaxT(s, 100)) expect(w).toBeCloseTo(1 / 3, 2);
  });
  it('refuses a temperature that is not positive', () => {
    expect(() => softmaxT([1, 2], 0)).toThrow(/temperature/);
  });
  it('keeps the k largest weights and renormalises them to one', () => {
    const w = topK([0.5, 0.3, 0.15, 0.05], 2);
    expect(w[0]).toBeCloseTo(0.625, 12);
    expect(w[1]).toBeCloseTo(0.375, 12);
    expect(w.slice(2)).toEqual([0, 0]);
  });
});

describe('fitGate', () => {
  // Two experts, each right in its own region: a fitted gate must learn to route.
  const toy = () => {
    const features = [], predictions = [], targets = [];
    for (let i = 0; i < 40; i += 1) {
      const warm = i % 2 === 0;
      features.push({ userCount: warm ? 20 : 0, movieCount: warm ? 30 : 0 });
      predictions.push(warm ? [4, 3] : [3, 2]);
      targets.push(warm ? 4 : 2);
    }
    return { features, predictions, targets };
  };
  it('cuts the error of the uniform gate it starts from by at least four times', () => {
    const { losses } = fitGate(toy());
    expect(losses.at(-1)).toBeLessThan(losses[0] / 4);
  });
  it('routes each region to the expert that is right there', () => {
    const data = toy();
    const { theta } = fitGate(data);
    mixturePredict(theta, data.features, data.predictions)
      .forEach((p, i) => expect(Math.abs(p - data.targets[i])).toBeLessThan(0.2));
  });
  it('is the same gate for the same data', () => {
    expect(fitGate(toy()).theta).toEqual(fitGate(toy()).theta);
  });
  it('reports how much weight each expert receives on average', () => {
    expect(utilisation([[1, 0], [0, 1]])).toEqual([0.5, 0.5]);
  });
});
