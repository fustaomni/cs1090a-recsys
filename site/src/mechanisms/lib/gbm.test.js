import { describe, expect, it } from "vitest";
import { gradientBoost } from "./boosting.js";
import { forestRatings } from "./ratings.js";

// Model 11's training rows: the first 200 of forestRatings({ seed: 141, n: 300 }), seed 3.
const FEATURES = ["user", "movie"];
const train = forestRatings({ seed: 141, n: 300 }).slice(0, 200);

describe("gradient boosting, as Model 11 shows it", () => {
  it("adds only a fraction nu of each tree to the prediction", () => {
    const options = { stages: 20, learningRate: 0.1, splits: 4, seed: 3 };
    const fit = gradientBoost(train, FEATURES, options);
    const row = train[0];
    expect(fit.steps).toHaveLength(20);
    for (let m = 1; m <= 20; m += 1) {
      const added = fit.predict(row, m) - fit.predict(row, m - 1);
      expect(added).toBeCloseTo(0.1 * fit.steps[m - 1].step(row), 12);
    }
  });

  it("can step past the rating scale, since a sum of trees is not bounded by it", () => {
    const corner = (user, movie, rating) =>
      Array.from({ length: 5 }, () => ({ user, movie, rating }));
    const rows = [...corner(1, 0, 5), ...corner(0, 1, 5), ...corner(0, 0, 1)];
    const fit = gradientBoost(rows, FEATURES, { stages: 60, learningRate: 0.5, splits: 1 });
    expect(fit.predict({ user: 1, movie: 1 })).toBeGreaterThan(5);
  });
});
