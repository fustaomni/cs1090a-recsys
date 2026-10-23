import { describe, expect, it } from "vitest";
import data from "../../data/movielens.json";
import { correlation, encodings, smoothed } from "./encoding.js";
import { constantErrors, errors, shares, weightedLine } from "./macro.js";
import { mulberry32, normal } from "./random.js";
import { timedRatings } from "./ratings.js";
import { byTime } from "./timecv.js";

const real = shares(data.splits["0.8/0.9"].training.counts);

describe("pooled against macro error", () => {
  it("gives the macro floors 1.20 and the square root of two at a constant 3", () => {
    const at3 = constantErrors(3, real);
    expect(at3.macroMae).toBeCloseTo(1.2, 12);
    expect(at3.macroRmse).toBeCloseTo(Math.SQRT2, 12);
  });

  it("makes the macro score of a constant independent of the class mix", () => {
    const uniform = [0.2, 0.2, 0.2, 0.2, 0.2];
    expect(constantErrors(3.6, real).macroRmse).toBe(constantErrors(3.6, uniform).macroRmse);
    const pooled = (mix) => constantErrors(3.6, mix).pooledRmse;
    expect(pooled(real)).not.toBe(pooled(uniform));
  });

  it("minimises pooled RMSE at the mean rating and macro RMSE at 3", () => {
    const mean = real.reduce((s, p, i) => s + p * (i + 1), 0);
    const grid = Array.from({ length: 401 }, (_, i) => 1 + i / 100);
    const score = (c, key) => constantErrors(c, real)[key];
    const best = (key) => grid.reduce((a, c) => (score(c, key) < score(a, key) ? c : a));
    expect(best("pooledRmse")).toBeCloseTo(mean, 2);
    expect(best("macroRmse")).toBeCloseTo(3, 2);
  });

  it("trades pooled error for macro error when training weights levels by 1 / n_k", () => {
    const rng = mulberry32(4);
    const actual = Array.from({ length: 4000 }, () => {
      const u = rng();
      let k = 0;
      let running = real[0];
      while (u > running) running += real[(k += 1)];
      return k + 1;
    });
    const signal = actual.map((y) => y + 1.2 * normal(rng));
    const plain = weightedLine(signal, actual, false);
    const balanced = weightedLine(signal, actual, true);
    const a = errors(signal.map(plain), actual);
    const b = errors(signal.map(balanced), actual);
    expect(b.macroRmse).toBeLessThan(a.macroRmse);
    expect(b.pooledRmse).toBeGreaterThan(a.pooledRmse);
  });
});

describe("encoding a user's history", () => {
  it("falls back to the global mean with no history and to the user's mean as m shrinks", () => {
    expect(smoothed(0, 4.5, 10, 3.6)).toBe(3.6);
    expect(smoothed(20, 4.5, 1e-9, 3.6)).toBeCloseTo(4.5, 6);
  });

  it("uses only earlier ratings in the prior-only encoding", () => {
    const rows = [
      { user: 1, rating: 5 },
      { user: 1, rating: 1 },
      { user: 1, rating: 3 },
    ];
    const coded = encodings(rows, 0, 3);
    expect(coded[1].prior).toBe(5);
    expect(coded[2].prior).toBe(3);
    expect(coded[0].earlier).toBe(0);
  });

  it("flatters the naive encoding in sample, the leak the prior-only one avoids", () => {
    const rows = byTime(timedRatings());
    const mu = rows.reduce((s, r) => s + r.rating, 0) / rows.length;
    const coded = encodings(rows, 2, mu);
    const ys = rows.map((r) => r.rating);
    const naive = correlation(coded.map((c) => c.naive), ys);
    const prior = correlation(coded.map((c) => c.prior), ys);
    expect(naive - prior).toBeGreaterThan(0.1);
  });
});
