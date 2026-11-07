// site/src/mechanisms/lib/crossed.test.js
import { describe, expect, it } from "vitest";
import { CROSSED, crossedFit, crossedRatings, kept } from "./crossed.js";

const { rows, movieOffsets } = crossedRatings();

function correlation(a, b) {
  const mean = (values) => values.reduce((total, value) => total + value, 0) / values.length;
  const ma = mean(a);
  const mb = mean(b);
  const cov = a.reduce((total, value, index) => total + (value - ma) * (b[index] - mb), 0);
  const va = a.reduce((total, value) => total + (value - ma) ** 2, 0);
  const vb = b.reduce((total, value) => total + (value - mb) ** 2, 0);
  return cov / Math.sqrt(va * vb);
}

describe("crossed random-effects bias model (A.246)", () => {
  it("shrinks the offsets as a whole toward zero as the pooling grows", () => {
    // A crossed fit trades user and movie offsets against each other, so one offset can move
    // away from zero; the penalised solution as a vector shrinks, and vanishes as pooling grows.
    const size = (fit) => Math.hypot(...fit.users, ...fit.movies);
    const raw = crossedFit(rows, { pooling: 0 });
    const light = crossedFit(rows, { pooling: 1 });
    const heavy = crossedFit(rows, { pooling: 500 });
    expect(size(light)).toBeLessThan(size(raw));
    expect(size(heavy)).toBeLessThan(size(light));
    for (const offset of [...heavy.users, ...heavy.movies]) {
      expect(Math.abs(offset)).toBeLessThan(0.05);
    }
  });

  it("lets a user with more ratings keep more of their own offset", () => {
    expect(kept(2, 3)).toBeLessThan(kept(9, 3));
    expect(kept(0, 3)).toBe(0);
    expect(kept(5, 0)).toBe(1);
  });

  it("has converged: more alternating updates change nothing", () => {
    const short = crossedFit(rows, { pooling: 1, iterations: 60 });
    const long = crossedFit(rows, { pooling: 1, iterations: 300 });
    for (let movie = 0; movie < CROSSED.movies; movie += 1) {
      expect(short.movies[movie]).toBeCloseTo(long.movies[movie], 6);
    }
  });

  it("recovers the true movie offsets it was generated from", () => {
    const fit = crossedFit(rows, { pooling: 1 });
    expect(correlation(fit.movies, movieOffsets)).toBeGreaterThan(0.6);
  });
});
