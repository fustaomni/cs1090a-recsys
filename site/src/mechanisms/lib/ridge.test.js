import { describe, expect, it } from "vitest";
import { eigen2, moments, prepared, ridge } from "./penalized.js";
import { mulberry32, resample } from "./random.js";
import { ratings } from "./ratings.js";
import { mean } from "./stats.js";

// Model 4's data and fit: the first 120 of ratings({ seed: 51, n: 150, rho: 0.9 }).
const KEYS = ["user", "movie"];
const rows = ratings({ seed: 51, n: 150, rho: 0.9 }).slice(0, 120);
const train = prepared(rows, KEYS);
const sums = moments(train.xs, train.ys);

describe("ridge, as Model 4 shows it", () => {
  it("standardises each predictor on the rows it is given, to mean 0 and variance 1", () => {
    for (const j of [0, 1]) {
      const column = train.xs.map((x) => x[j]);
      expect(mean(column)).toBeCloseTo(0, 10);
      expect(mean(column.map((v) => v * v))).toBeCloseTo(1, 10);
    }
    expect(mean(train.ys)).toBeCloseTo(0, 10);
  });

  it("keeps d / (d + lambda) of least squares along each eigen-direction", () => {
    const lambda = 0.1;
    const [large, small] = eigen2(sums.gram);
    const ols = ridge(sums, 0);
    const shrunk = ridge(sums, lambda);
    const [[a, b]] = sums.gram;
    expect(large).toBeGreaterThan(small);
    for (const d of [large, small]) {
      const v = [b, d - a];
      const norm = Math.hypot(v[0], v[1]);
      const along = (w) => (w[0] * v[0] + w[1] * v[1]) / norm;
      expect(along(shrunk)).toBeCloseTo((d / (d + lambda)) * along(ols), 10);
    }
  });

  it("scatters resampled fits less than least squares does", () => {
    const rng = mulberry32(2001);
    const fits = Array.from({ length: 30 }, () => {
      const picked = resample(rng, rows.length).map((i) => rows[i]);
      const sample = prepared(picked, KEYS);
      const sampleSums = moments(sample.xs, sample.ys);
      return { ols: ridge(sampleSums, 0), ridge: ridge(sampleSums, 0.1) };
    });
    const sd = (values) => {
      const centre = mean(values);
      return Math.sqrt(mean(values.map((v) => (v - centre) ** 2)));
    };
    for (const k of [0, 1]) {
      const shrunk = sd(fits.map((fit) => fit.ridge[k]));
      expect(shrunk).toBeLessThan(sd(fits.map((fit) => fit.ols[k])));
    }
  });
});
