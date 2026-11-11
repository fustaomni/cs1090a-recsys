import { describe, expect, it } from "vitest";
import { dot, normalEquations } from "./linalg.js";
import { mulberry32, resample } from "./random.js";
import { historyRatings, ratings } from "./ratings.js";
import { design, fit, heldFit, predict, residuals, vif } from "./regression.js";
import { mean } from "./stats.js";

const solve2 = ([[a, b], [c, d]], [e, f]) => {
  const det = a * d - b * c;
  return [(d * e - b * f) / det, (a * f - c * e) / det];
};

describe("least squares by QR", () => {
  const rows = ratings({ n: 400, rho: 0.6 });
  const ys = rows.map((row) => row.rating);
  const ubar = mean(rows.map((row) => row.user));
  const fbar = mean(rows.map((row) => row.movie));
  const terms = [
    { name: "user", value: (row) => row.user - ubar },
    { name: "movie", value: (row) => row.movie - fbar },
  ];
  const coef = fit(rows, terms, ys);

  it("solves the centred normal equations, with the intercept at the mean rating", () => {
    const centred = rows.map((row) => [row.user - ubar, row.movie - fbar]);
    const { gram, moment } = normalEquations(centred, ys);
    const [w1, w2] = solve2(gram, moment);
    expect(coef[1]).toBeCloseTo(w1, 10);
    expect(coef[2]).toBeCloseTo(w2, 10);
    expect(coef[0]).toBeCloseTo(mean(ys), 10);
  });

  it("leaves residuals orthogonal to every column of the design", () => {
    const left = residuals(coef, terms, rows, ys);
    for (const column of [0, 1, 2]) {
      const values = design(rows, terms).map((row) => row[column]);
      expect(dot(left, values)).toBeCloseTo(0, 8);
    }
  });

  it("refuses a column that is a linear combination of the others", () => {
    const twice = [...terms, { name: "twice", value: (row) => 2 * (row.user - ubar) }];
    expect(() => fit(rows, twice, ys)).toThrow(/linear combination/);
  });

  it("satisfies the normal equations X'X b = X'y", () => {
    const designRows = design(rows, terms);
    const { gram, moment } = normalEquations(designRows, ys);
    const residual = gram.map((row, i) => dot(row, coef) - moment[i]);
    expect(Math.max(...residual.map(Math.abs))).toBeLessThan(1e-8);
  });
});

describe("collinearity", () => {
  it("raises the VIF of correlated predictors to about 1 / (1 - rho^2)", () => {
    const rows = ratings({ n: 20000, rho: 0.8 });
    const terms = [
      { value: (row) => row.user },
      { value: (row) => row.movie },
    ];
    const [first, second] = vif(rows, terms);
    expect(first).toBeCloseTo(1 / (1 - 0.64), 0);
    expect(second).toBeCloseTo(first, 6);
  });

  it("spreads resampled coefficients more as the predictors correlate", () => {
    const spread = (rho) => {
      const rows = ratings({ n: 300, rho });
      const ys = rows.map((row) => row.rating);
      const rng = mulberry32(5);
      const terms = [{ value: (row) => row.user }, { value: (row) => row.movie }];
      const slopes = Array.from({ length: 60 }, () => {
        const picked = resample(rng, rows.length);
        return fit(picked.map((i) => rows[i]), terms, picked.map((i) => ys[i]))[1];
      });
      const centre = mean(slopes);
      return Math.sqrt(mean(slopes.map((s) => (s - centre) ** 2)));
    };
    expect(spread(0.9)).toBeGreaterThan(1.5 * spread(0));
  });

  it("trades the slopes off along the valley as the predictors correlate", () => {
    const rows = ratings({ n: 300, rho: 0.9 });
    const ys = rows.map((row) => row.rating);
    const rng = mulberry32(7);
    const terms = [{ value: (row) => row.user }, { value: (row) => row.movie }];
    const pairs = Array.from({ length: 60 }, () => {
      const picked = resample(rng, rows.length);
      const coef = fit(picked.map((i) => rows[i]), terms, picked.map((i) => ys[i]));
      return [coef[1], coef[2]];
    });
    const first = pairs.map((pair) => pair[0]);
    const second = pairs.map((pair) => pair[1]);
    const a = mean(first);
    const b = mean(second);
    const covariance = mean(pairs.map(([x, y]) => (x - a) * (y - b)));
    const sd = (values, centre) => Math.sqrt(mean(values.map((v) => (v - centre) ** 2)));
    expect(covariance / (sd(first, a) * sd(second, b))).toBeLessThan(-0.5);
  });
});

describe("polynomial terms with the curvature held", () => {
  const rows = historyRatings({ seed: 21, n: 400 });
  const ys = rows.map((row) => row.rating);
  const ubar = mean(rows.map((row) => row.user));
  const cbar = mean(rows.map((row) => row.count));
  const termsAt = (u0, c0) => [
    { key: "user", value: (row) => row.user - u0 },
    { key: "count", value: (row) => row.count - c0 },
    { key: "square", value: (row) => (row.count - c0) ** 2 },
    { key: "both", value: (row) => (row.user - u0) * (row.count - c0) },
  ];
  const drawn = (terms) => {
    const coef = heldFit(rows, ys, terms, { square: 0.1, both: -0.2 });
    const vector = [coef.intercept, ...terms.map((term) => coef[term.key])];
    return rows.slice(0, 50).map((row) => predict(vector, terms, row));
  };

  it("draws the same surface whether or not the predictors are centred", () => {
    const centred = drawn(termsAt(ubar, cbar));
    const raw = drawn(termsAt(0, 0));
    expect(centred).toHaveLength(50);
    centred.forEach((value, index) => expect(value).toBeCloseTo(raw[index], 8));
  });

  it("draws its ratings on the five integer levels", () => {
    expect(ys).toHaveLength(400);
    expect(ys.every((y) => Number.isInteger(y) && y >= 1 && y <= 5)).toBe(true);
  });
});

describe("the multi-linear bowl", () => {
  const rows = ratings({ seed: 31, n: 300, rho: 0.6 });
  const ys = rows.map((row) => row.rating);
  const ybar = mean(ys);
  const ubar = mean(rows.map((row) => row.user));
  const fbar = mean(rows.map((row) => row.movie));
  const xs = rows.map((row) => [row.user - ubar, row.movie - fbar]);
  const deviations = ys.map((y) => y - ybar);
  const { gram, moment } = normalEquations(xs, deviations);
  const syy = dot(deviations, deviations);
  const left = (a, b) => xs.map(([u, f], i) => deviations[i] - a * u - b * f);

  it("is the sum of squared residuals, expanded through the normal equations", () => {
    for (const [a, b] of [[0.2, 0.9], [0.5, 0.5], [-0.2, 1.2]]) {
      const across = a * moment[0] + b * moment[1];
      const curved = a * a * gram[0][0] + 2 * a * b * gram[0][1] + b * b * gram[1][1];
      const direct = left(a, b).reduce((total, r) => total + r * r, 0);
      expect(syy - 2 * across + curved).toBeCloseTo(direct, 8);
    }
  });

  it("leaves residuals summing to zero for any slopes once the intercept is the mean", () => {
    for (const [a, b] of [[0.2, 0.9], [1.1, -0.1]]) {
      expect(left(a, b).reduce((total, r) => total + r, 0)).toBeCloseTo(0, 8);
    }
  });
});

describe("polynomial and interaction terms", () => {
  const rows = historyRatings({ n: 600 });
  const ys = rows.map((row) => row.rating);
  const ubar = mean(rows.map((row) => row.user));
  const cbar = mean(rows.map((row) => row.count));
  const build = (u0, c0) => [
    { value: (row) => row.user - u0 },
    { value: (row) => row.count - c0 },
    { value: (row) => (row.count - c0) ** 2 },
    { value: (row) => (row.user - u0) * (row.count - c0) },
  ];
  const raw = build(0, 0);
  const centred = build(ubar, cbar);
  const rawCoef = fit(rows, raw, ys);
  const centredCoef = fit(rows, centred, ys);

  it("predicts exactly the same after centring", () => {
    for (const row of rows.slice(0, 50)) {
      expect(predict(centredCoef, centred, row)).toBeCloseTo(predict(rawCoef, raw, row), 8);
    }
  });

  it("keeps the curvature and interaction coefficients, shifting only the lower ones", () => {
    expect(centredCoef[3]).toBeCloseTo(rawCoef[3], 8);
    expect(centredCoef[4]).toBeCloseTo(rawCoef[4], 8);
    expect(Math.abs(centredCoef[2] - rawCoef[2])).toBeGreaterThan(0.01);
  });

  it("cuts the VIF that uncentred powers of count create", () => {
    const before = vif(rows, raw);
    const after = vif(rows, centred);
    expect(before[1]).toBeGreaterThan(5);
    expect(after[1]).toBeLessThan(before[1] / 2);
  });

  it("never raises training error as terms are added", () => {
    const rmse = (terms) => {
      const coef = fit(rows, terms, ys);
      const left = residuals(coef, terms, rows, ys);
      return Math.sqrt(mean(left.map((r) => r * r)));
    };
    const linear = rmse(centred.slice(0, 2));
    const square = rmse(centred.slice(0, 3));
    const all = rmse(centred);
    expect(square).toBeLessThanOrEqual(linear);
    expect(all).toBeLessThanOrEqual(square);
  });
});
