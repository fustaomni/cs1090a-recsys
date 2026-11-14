import { describe, expect, it } from "vitest";
import { lambdaMax, lasso, prepared } from "./penalized.js";
import { mulberry32, subsample } from "./random.js";
import { selectionRatings } from "./ratings.js";

// Model 5's data: the first 160 of selectionRatings({ seed: 61, n: 200 }), here at rho 0.95.
const KEYS = ["user", "movie", "noise"];

describe("lasso, as Model 5 shows it", () => {
  it("lets the two correlated histories trade places across half-samples at high rho", () => {
    const rows = selectionRatings({ seed: 61, n: 200, rho: 0.95 }).slice(0, 160);
    const rng = mulberry32(77);
    let userOnly = 0;
    let movieOnly = 0;
    for (let draw = 0; draw < 100; draw += 1) {
      const half = subsample(rng, rows.length, rows.length / 2).map((index) => rows[index]);
      const { xs, ys } = prepared(half, KEYS);
      const [user, movie] = lasso(xs, ys, 0.9 * lambdaMax(xs, ys)).coef;
      if (user !== 0 && movie === 0) userOnly += 1;
      if (movie !== 0 && user === 0) movieOnly += 1;
    }
    expect(userOnly).toBeGreaterThan(0);
    expect(movieOnly).toBeGreaterThan(0);
  });
});
