import { describe, expect, it } from "vitest";
import {
  calibrationBins,
  calibrationSlope,
  decomposition,
  errorByLevel,
} from "./calibration.js";
import { surfaceRatings, trueSurface } from "./ratings.js";
import { grow, view } from "./tree.js";

describe("shrinkage and calibration", () => {
  const rows = surfaceRatings({ n: 4000 });
  const truth = rows.map(trueSurface);
  const actual = rows.map((r) => r.rating);

  it("slants error by level even for the true conditional mean", () => {
    const [one, , , , five] = errorByLevel(truth, actual);
    expect(one.mean).toBeGreaterThan(0.5);
    expect(five.mean).toBeLessThan(-0.5);
  });

  it("is calibrated with slope near one for the true conditional mean", () => {
    expect(calibrationSlope(truth, actual)).toBeGreaterThan(0.85);
    expect(calibrationSlope(truth, actual)).toBeLessThan(1.15);
  });

  it("reads excess shrinkage as a slope above one", () => {
    const mean = actual.reduce((s, y) => s + y, 0) / actual.length;
    const flattened = truth.map((t) => mean + 0.5 * (t - mean));
    expect(calibrationSlope(flattened, actual)).toBeGreaterThan(1.6);
  });

  it("leaves the slope undefined for a constant prediction", () => {
    expect(calibrationSlope(truth.map(() => 3.6), actual)).toBeNaN();
  });

  it("bins rows by predicted value in increasing order", () => {
    const bins = calibrationBins(truth, actual, 6);
    for (let b = 1; b < bins.length; b += 1) {
      expect(bins[b].predicted).toBeGreaterThanOrEqual(bins[b - 1].predicted);
    }
  });
});

describe("bias and variance on synthetic data", () => {
  const queries = surfaceRatings({ seed: 5, n: 60 });
  const fitsAt = (steps) =>
    Array.from({ length: 12 }, (_, d) => {
      const tree = grow(surfaceRatings({ seed: 300 + d, n: 300 }), ["user", "movie"], {
        minLeaf: 3,
      });
      return view(tree, { steps }).predict;
    });

  it("trades bias for variance as the tree grows", () => {
    const simple = decomposition(fitsAt(1), queries, trueSurface, 0.49);
    const complex = decomposition(fitsAt(60), queries, trueSurface, 0.49);
    expect(complex.bias).toBeLessThan(simple.bias);
    expect(complex.variance).toBeGreaterThan(simple.variance);
  });

  it("keeps the constant's variance tiny: only the mean moves between datasets", () => {
    const constant = decomposition(fitsAt(0), queries, trueSurface, 0.49);
    expect(constant.variance).toBeLessThan(0.01);
  });
});
