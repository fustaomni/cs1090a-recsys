import { describe, expect, it } from "vitest";
import { crossedRatings, percentile, replicates } from "./inference.js";

// Technique 10's data: crossedRatings({ seed: 171, users: 60, movies: 40, shared }), its
// replicates seeded 29 and its width sweep, 300 replicates, seeded 31.
const interval = (values) => [percentile(values, 0.025), percentile(values, 0.975)];

function draws(shared, count, seed) {
  const data = crossedRatings({ seed: 171, users: 60, movies: 40, shared });
  return replicates(data.rows, "user", data.users, data.movies, count, seed);
}

describe("the paired test, as Technique 10 shows it", () => {
  it("overlaps the marginal intervals while the paired one excludes zero, at the defaults", () => {
    const runs = draws(0.7, 1000, 29);
    const [aLow, aHigh] = interval(runs.map((r) => r.a));
    const [bLow, bHigh] = interval(runs.map((r) => r.b));
    const [pairedLow] = interval(runs.map((r) => r.difference));
    expect(aLow <= bHigh && bLow <= aHigh).toBe(true);
    expect(pairedLow).toBeGreaterThan(0);
  });

  it("narrows the paired interval as the two models share more of their error", () => {
    const width = (shared) => {
      const [low, high] = interval(draws(shared, 300, 31).map((r) => r.difference));
      return high - low;
    };
    expect(width(0.95)).toBeLessThan(width(0));
  });
});
