import { describe, expect, it } from "vitest";
import {
  crossedRatings,
  percentile,
  replicates,
  schemeWeights,
  weightedRmse,
} from "./inference.js";
import { mulberry32 } from "./random.js";
import { stackingRatings } from "./ratings.js";
import { ambiguity, correlation, metaFit, metaObjective } from "./stacking.js";

describe("resampling crossed ratings", () => {
  const { rows, users, films } = crossedRatings({ users: 40, films: 30 });

  it("gives row, user and pigeonhole weights with the right structure", () => {
    const rng = mulberry32(1);
    const row = schemeWeights(rows, "row", users, films, rng);
    expect(row.reduce((s, w) => s + w, 0)).toBe(rows.length);
    const user = schemeWeights(rows, "user", users, films, rng);
    rows.forEach((r, i) => {
      const j = rows.findIndex((other) => other.user === r.user);
      expect(user[i]).toBe(user[j]);
    });
    const pigeon = schemeWeights(rows, "pigeonhole", users, films, mulberry32(2));
    const again = mulberry32(2);
    const userCounts = new Array(users).fill(0);
    for (let i = 0; i < users; i += 1) userCounts[Math.floor(again() * users)] += 1;
    const filmCounts = new Array(films).fill(0);
    for (let i = 0; i < films; i += 1) filmCounts[Math.floor(again() * films)] += 1;
    rows.forEach((r, i) => expect(pigeon[i]).toBe(userCounts[r.user] * filmCounts[r.film]));
  });

  it("computes the plain RMSE when every weight is one", () => {
    const plain = Math.sqrt(rows.reduce((s, r) => s + (r.a - r.rating) ** 2, 0) / rows.length);
    expect(weightedRmse(rows, "a", rows.map(() => 1))).toBeCloseTo(plain, 12);
  });

  it("interpolates percentiles", () => {
    expect(percentile([1, 2, 3, 4, 5], 0.5)).toBe(3);
    expect(percentile([0, 10], 0.25)).toBeCloseTo(2.5, 12);
  });

  it("widens the paired interval as users, then users and films, are resampled", () => {
    const width = (scheme) => {
      const values = replicates(rows, scheme, users, films, 400, 7).map((r) => r.difference);
      return percentile(values, 0.975) - percentile(values, 0.025);
    };
    expect(width("user")).toBeGreaterThan(width("row"));
    expect(width("pigeonhole")).toBeGreaterThan(width("user"));
  });

  it("narrows the paired difference below either model's own interval", () => {
    const draws = replicates(rows, "user", users, films, 300, 8);
    const width = (values) => percentile(values, 0.975) - percentile(values, 0.025);
    const paired = width(draws.map((r) => r.difference));
    expect(paired).toBeLessThan(width(draws.map((r) => r.a)));
    expect(paired).toBeLessThan(width(draws.map((r) => r.b)));
  });
});

describe("stacking", () => {
  const rows = stackingRatings({ n: 400, correlation: 0.8 });
  const predictions = rows.map((r) => r.base);
  const ys = rows.map((r) => r.rating);

  it("keeps the unconstrained solution when it is already non-negative", () => {
    const ols = metaFit(predictions, ys, { method: "ols" });
    if (ols.w.every((v) => v >= 0)) {
      expect(metaFit(predictions, ys, { method: "nnls" }).w).toEqual(ols.w);
    }
  });

  it("finds the constrained minimum when a weight wants to go negative", () => {
    const flipped = rows.map((r) => [r.base[0], 2 * r.base[0] - r.base[1]]);
    const ols = metaFit(flipped, ys, { method: "ols" });
    const nnls = metaFit(flipped, ys, { method: "nnls" });
    expect(ols.w.some((v) => v < 0)).toBe(true);
    expect(nnls.w.every((v) => v >= 0)).toBe(true);
    for (const a of [0, 0.3, 0.6, 1]) {
      for (const b of [0, 0.2, 0.5]) {
        expect(metaObjective(nnls.stats, nnls.w, 0)).toBeLessThanOrEqual(
          metaObjective(nnls.stats, [a, b], 0) + 1e-12,
        );
      }
    }
  });

  it("makes the weights sum to one when asked", () => {
    const fit = metaFit(predictions, ys, { method: "ridge", lambda: 0.05, sumToOne: true });
    expect(fit.w.reduce((s, v) => s + v, 0)).toBeCloseTo(1, 10);
  });

  it("splits ensemble error into member error minus ambiguity", () => {
    const { member, spread, ensemble } = ambiguity(predictions, ys, [0.5, 0.5]);
    expect(member - spread).toBeCloseTo(ensemble, 10);
  });

  it("measures the correlation of the two models' errors", () => {
    const errors = (j) => rows.map((r) => r.base[j] - r.rating);
    expect(correlation(errors(0), errors(1))).toBeGreaterThan(0.3);
  });
});
