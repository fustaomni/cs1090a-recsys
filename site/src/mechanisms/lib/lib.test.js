import { describe, expect, it } from "vitest";
import { fixed } from "./format.js";
import { steps, surface } from "./grid.js";
import { clip, outOfRange, rmse } from "./metrics.js";
import { mulberry32 } from "./random.js";
import { TRUTH, ratings } from "./ratings.js";
import { covariance, mean, simpleFit, sse, sums, variance } from "./stats.js";

describe("seeded data", () => {
  it("draws the same numbers for the same seed, all in [0, 1)", () => {
    const first = Array.from({ length: 5 }, mulberry32(42));
    const again = Array.from({ length: 5 }, mulberry32(42));
    expect(first).toEqual(again);
    expect(first.every((value) => value >= 0 && value < 1)).toBe(true);
  });

  it("gives ratings only on the five integer levels", () => {
    const levels = new Set(ratings({ n: 2000 }).map((row) => row.rating));
    expect([...levels].every((level) => [1, 2, 3, 4, 5].includes(level))).toBe(true);
    expect(ratings({ seed: 3 })).toEqual(ratings({ seed: 3 }));
  });
});

describe("simple least squares", () => {
  const rows = ratings({ n: 500 });
  const xs = rows.map((row) => row.user);
  const ys = rows.map((row) => row.rating);
  const fit = simpleFit(xs, ys);

  it("has slope cov/var and intercept the mean rating once x is centred", () => {
    expect(fit.b1).toBeCloseTo(covariance(xs, ys) / variance(xs), 12);
    expect(fit.b0).toBeCloseTo(mean(ys), 12);
  });

  it("leaves residuals summing to zero and orthogonal to x", () => {
    const residuals = xs.map((x, index) => ys[index] - fit.b0 - fit.b1 * (x - fit.xbar));
    expect(residuals.reduce((total, r) => total + r, 0)).toBeCloseTo(0, 9);
    const cross = residuals.reduce((total, r, index) => total + r * (xs[index] - fit.xbar), 0);
    expect(cross).toBeCloseTo(0, 9);
  });

  it("computes the same SSE from sums as directly, and is the bowl's lowest point", () => {
    const totals = sums(xs, ys);
    const direct = (b0, b1) =>
      xs.reduce((total, x, index) => total + (ys[index] - b0 - b1 * (x - fit.xbar)) ** 2, 0);
    expect(sse(totals, 3.1, 0.7)).toBeCloseTo(direct(3.1, 0.7), 8);
    const lowest = sse(totals, fit.b0, fit.b1);
    for (const [d0, d1] of [[0.05, 0], [-0.05, 0], [0, 0.05], [0, -0.05]]) {
      expect(sse(totals, fit.b0 + d0, fit.b1 + d1)).toBeGreaterThan(lowest);
    }
  });
});

describe("omitted-variable bias", () => {
  const slopeAt = (rho) => {
    const rows = ratings({ n: 40000, rho, levels: false });
    return simpleFit(rows.map((row) => row.user), rows.map((row) => row.rating)).b1;
  };

  it("recovers the user effect when movie history is uncorrelated", () => {
    expect(slopeAt(0)).toBeCloseTo(TRUTH.user, 1);
  });

  it("absorbs rho times the movie effect when movie history is correlated", () => {
    expect(Math.abs(slopeAt(0.6) - (TRUTH.user + TRUTH.movie * 0.6))).toBeLessThan(0.03);
  });
});

describe("errors in and out of range", () => {
  it("counts predictions outside [1, 5] and never scores worse after clipping", () => {
    const predictions = [0.4, 2, 5.6, 4];
    const actual = [1, 2, 5, 4];
    expect(outOfRange(predictions)).toBe(2);
    expect(rmse(predictions.map(clip), actual)).toBeLessThanOrEqual(rmse(predictions, actual));
  });

  it("samples a surface with rows along y", () => {
    const grid = surface(steps(0, 1, 3), steps(0, 2, 2), (x, y) => x + 10 * y);
    expect(grid).toEqual([[0, 0.5, 1], [20, 20.5, 21]]);
  });
});

describe("number formatting", () => {
  it("never prints a negative zero", () => {
    expect(fixed(-0.0000004)).toBe("0.000");
    expect(fixed(-1.23456, 2)).toBe("-1.23");
  });
});
