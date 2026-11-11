import { describe, expect, it } from "vitest";
import { calibrationSlope } from "./calibration.js";
import { rmse } from "./metrics.js";
import { surfaceRatings, trueSurface } from "./ratings.js";
import { grow, view } from "./tree.js";
import { curve, oneStandardError, rollingFolds } from "./tuning.js";

// Technique 6's data at its defaults: surfaceRatings({ seed: 191, n: 300, noise: 0.7 }).
const FEATURES = ["user", "movie"];
const rows = surfaceRatings({ seed: 191, n: 300, noise: 0.7 });
const train = rows.slice(0, 240);
const later = rows.slice(240);

describe("bias and variance, as Technique 6 shows them", () => {
  it("lets fold error fall and then rise as splits are added", () => {
    const splits = Array.from({ length: 41 }, (_, s) => s);
    const points = curve(splits, rollingFolds(240, 5), (fold, s) => {
      const tree = grow(
        fold.train.map((i) => train[i]),
        FEATURES,
        { minLeaf: 3 },
      );
      const predict = view(tree, { steps: s }).predict;
      const held = fold.valid.map((i) => train[i]);
      return rmse(held.map(predict), held.map((r) => r.rating));
    });
    const { best } = oneStandardError(points, (a, b) => a.lambda < b.lambda);
    expect(best.lambda).toBeGreaterThan(0);
    expect(best.error).toBeLessThan(points[0].error);
    expect(best.error).toBeLessThan(points[40].error);
  });

  it("spreads the deepest tree's later predictions wider than the data supports", () => {
    const predict = view(grow(train, FEATURES, { minLeaf: 3 }), { steps: 40 }).predict;
    const slope = calibrationSlope(later.map(predict), later.map((r) => r.rating));
    expect(slope).toBeLessThan(1);
  });

  it("finds more noise in the rounded ratings than the latent sigma squared", () => {
    const many = surfaceRatings({ seed: 191, n: 4000, noise: 0.7 });
    const squares = many.reduce((s, r) => s + (r.rating - trueSurface(r)) ** 2, 0);
    // Rounding alone would add about 1/12; clipping to 1..5 removes part of that.
    expect(squares / many.length).toBeGreaterThan(0.49);
    expect(squares / many.length).toBeLessThan(0.49 + 1 / 12);
  });
});
