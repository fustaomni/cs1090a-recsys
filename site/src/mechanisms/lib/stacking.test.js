import { describe, expect, it } from "vitest";
import { stackingRatings } from "./ratings.js";
import { correlation, metaFit } from "./stacking.js";

// Model 12's meta-training rows: blocks two to four of stackingRatings({ seed: 161, n: 500 }).
const meta = (rho) => stackingRatings({ seed: 161, n: 500, correlation: rho }).slice(100, 400);
const bases = (rows) => rows.map((r) => r.base);
const ratings = (rows) => rows.map((r) => r.rating);
const errorCorrelation = (rows) =>
  correlation(
    rows.map((r) => r.base[0] - r.rating),
    rows.map((r) => r.base[1] - r.rating),
  );

describe("stacking, as Model 12 shows it", () => {
  it("keeps the errors more correlated than the slider sets, through the rating noise they share", () => {
    expect(errorCorrelation(meta(0.8))).toBeGreaterThan(0.8);
    expect(errorCorrelation(meta(0))).toBeGreaterThan(0.5);
  });

  it("pulls the two weights toward each other as the ridge penalty grows", () => {
    const rows = meta(0.8);
    const gap = (lambda) => {
      const { w } = metaFit(bases(rows), ratings(rows), { method: "ridge", lambda });
      return Math.abs(w[0] - w[1]);
    };
    const gaps = [0.001, 0.01, 0.1, 1].map(gap);
    for (let k = 1; k < gaps.length; k += 1) expect(gaps[k]).toBeLessThan(gaps[k - 1]);
  });

  it("sets a weight exactly to zero only where the constraint binds", () => {
    const rows = meta(0.8);
    const free = metaFit(bases(rows), ratings(rows), { method: "ridge", lambda: 0.1 });
    expect(free.w.every((v) => v > 0)).toBe(true);
    expect(free.binding.some(Boolean)).toBe(false);
    const flipped = rows.map((r) => [r.base[0], 2 * r.base[0] - r.base[1]]);
    const bound = metaFit(flipped, ratings(rows), { method: "nnls" });
    expect(bound.w.some((v) => v === 0)).toBe(true);
    bound.w.forEach((v, j) => {
      if (v === 0) expect(bound.unconstrained[j]).toBeLessThan(0);
      expect(bound.binding[j]).toBe(v === 0);
    });
  });

  it("keeps an unpenalised intercept when the weights sum to one", () => {
    const rows = meta(0.8);
    const predictions = bases(rows);
    const ys = ratings(rows);
    const fit = metaFit(predictions, ys, { method: "ridge", lambda: 0.1, sumToOne: true });
    const n = ys.length;
    const ybar = ys.reduce((s, y) => s + y, 0) / n;
    const pbar = [0, 1].map((j) => predictions.reduce((s, p) => s + p[j], 0) / n);
    expect(fit.w[0] + fit.w[1]).toBeCloseTo(1, 10);
    expect(fit.intercept).toBeCloseTo(ybar - pbar[0] * fit.w[0] - pbar[1] * fit.w[1], 10);
    expect(Math.abs(fit.intercept)).toBeGreaterThan(1e-6);
  });
});
