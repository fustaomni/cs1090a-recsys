import { describe, expect, it } from "vitest";
import {
  eigen2,
  kkt,
  lambdaMax,
  lasso,
  moments,
  ridge,
  prepared,
  softThreshold,
} from "./penalized.js";
import { mulberry32, subsample } from "./random.js";
import { ratings, selectionRatings } from "./ratings.js";
import { curve, logGrid, oneStandardError, rollingFolds } from "./tuning.js";

describe("ridge", () => {
  const { xs, ys } = prepared(ratings({ n: 200, rho: 0.9 }), ["user", "film"]);
  const sums = moments(xs, ys);

  it("is least squares at lambda = 0 and solves (X'X/n + lambda I) b = X'y/n", () => {
    const ols = ridge(sums, 0);
    const lambda = 0.7;
    const b = ridge(sums, lambda);
    sums.gram.forEach((row, i) => {
      const left = row.reduce((s, g, j) => s + g * b[j], 0) + lambda * b[i];
      expect(left).toBeCloseTo(sums.cross[i], 10);
      expect(row.reduce((s, g, j) => s + g * ols[j], 0)).toBeCloseTo(sums.cross[i], 10);
    });
  });

  it("pulls correlated coefficients toward each other, never exactly to zero", () => {
    const gaps = [0, 0.5, 5, 50].map((lambda) => {
      const [first, second] = ridge(sums, lambda);
      expect(first).not.toBe(0);
      expect(second).not.toBe(0);
      return Math.abs(first - second);
    });
    for (let k = 1; k < gaps.length; k += 1) expect(gaps[k]).toBeLessThan(gaps[k - 1]);
  });

  it("has effective degrees of freedom equal to the trace of its hat matrix", () => {
    const lambda = 0.3;
    const [e1, e2] = eigen2(sums.gram);
    const df = e1 / (e1 + lambda) + e2 / (e2 + lambda);
    const n = xs.length;
    const shifted = sums.gram.map((row, i) => row.map((g, j) => g + (i === j ? lambda : 0)));
    const [[a, b], [, d]] = shifted;
    const det = a * d - b * b;
    const inverse = [[d / det, -b / det], [-b / det, a / det]];
    const trace = xs.reduce((s, [u, f]) => {
      const left = [inverse[0][0] * u + inverse[0][1] * f, inverse[1][0] * u + inverse[1][1] * f];
      return s + (u * left[0] + f * left[1]) / n;
    }, 0);
    expect(df).toBeCloseTo(trace, 10);
  });
});

describe("lasso by coordinate descent", () => {
  const { xs, ys } = prepared(selectionRatings({ n: 300 }), ["user", "film", "noise"]);
  const top = lambdaMax(xs, ys);

  it("soft-thresholds: shrinks by lambda and zeroes anything within it", () => {
    expect(softThreshold(0.8, 0.3)).toBeCloseTo(0.5, 12);
    expect(softThreshold(-0.8, 0.3)).toBeCloseTo(-0.5, 12);
    expect(softThreshold(0.2, 0.3)).toBe(0);
  });

  it("satisfies the KKT conditions at its solution", () => {
    const { coef } = lasso(xs, ys, 0.3 * top);
    expect(kkt(xs, ys, coef, 0.3 * top).every((check) => check.holds)).toBe(true);
  });

  it("zeroes every coefficient from lambda_max up, and frees one just below it", () => {
    expect(lasso(xs, ys, top).coef.every((b) => b === 0)).toBe(true);
    expect(lasso(xs, ys, 0.98 * top).coef.filter((b) => b !== 0)).toHaveLength(1);
  });

  it("approaches least squares as lambda shrinks", () => {
    const ols = ridge(moments(xs, ys), 0);
    lasso(xs, ys, 1e-7).coef.forEach((b, j) => expect(b).toBeCloseTo(ols[j], 4));
  });

  it("records a path that starts at zero and ends at the solution", () => {
    const { coef, trace } = lasso(xs, ys, 0.2 * top);
    expect(trace[0]).toEqual([0, 0, 0]);
    expect(trace[trace.length - 1]).toEqual(coef);
  });
});

describe("selection and tuning", () => {
  it("draws subsamples without replacement", () => {
    const picked = subsample(mulberry32(3), 100, 50);
    expect(new Set(picked).size).toBe(50);
    expect(picked.every((index) => index >= 0 && index < 100)).toBe(true);
  });

  it("selects the irrelevant predictor far less often than the ones that matter", () => {
    const rows = selectionRatings({ n: 300 });
    const rng = mulberry32(9);
    const counts = [0, 0, 0];
    for (let draw = 0; draw < 100; draw += 1) {
      const half = subsample(rng, rows.length, rows.length / 2).map((index) => rows[index]);
      const { xs, ys } = prepared(half, ["user", "film", "noise"]);
      lasso(xs, ys, 0.3 * lambdaMax(xs, ys)).coef.forEach((b, j) => {
        if (b !== 0) counts[j] += 1;
      });
    }
    expect(counts[2]).toBeLessThan(counts[0]);
    expect(counts[2]).toBeLessThan(counts[1]);
  });

  it("validates every fold on rows later than all its training rows", () => {
    const folds = rollingFolds(100, 5);
    expect(folds).toHaveLength(4);
    for (const fold of folds) {
      expect(Math.max(...fold.train)).toBeLessThan(Math.min(...fold.valid));
    }
  });

  it("takes the largest lambda within one standard error of the minimum", () => {
    const points = logGrid(10, 0.01, 4).map((lambda, index) => ({
      lambda,
      error: [1.2, 1.0, 0.9, 0.95][index],
      se: 0.1,
    }));
    const { best, simplest } = oneStandardError(points);
    expect(best.error).toBe(0.9);
    expect(simplest.lambda).toBeCloseTo(10 ** (1 - 3 / 3), 10);
  });

  it("produces one curve point per lambda with a standard error", () => {
    const folds = rollingFolds(60, 4);
    const points = curve([1, 2], folds, (fold, lambda) => lambda + fold.valid.length / 100);
    expect(points).toHaveLength(2);
    expect(points[0].se).toBeGreaterThanOrEqual(0);
  });
});
