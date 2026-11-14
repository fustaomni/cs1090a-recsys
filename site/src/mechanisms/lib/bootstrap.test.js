import { describe, expect, it } from "vitest";
import { crossedRatings, percentile, replicates } from "./inference.js";

// Technique 9's data: crossedRatings({ seed: 151, users, movies: 40, shared }), 2000
// replicates per scheme seeded 23, at the page's defaults and its sliders' corners.
function differences(users, shared, scheme) {
  const data = crossedRatings({ seed: 151, users, movies: 40, shared });
  return replicates(data.rows, scheme, data.users, data.movies, 2000, 23).map(
    (r) => r.difference,
  );
}

const width = (values) => percentile(values, 0.975) - percentile(values, 0.025);

describe("bootstrap inference, as Technique 9 shows it", () => {
  const widths = (users, shared) => ({
    row: width(differences(users, shared, "row")),
    user: width(differences(users, shared, "user")),
    pigeonhole: width(differences(users, shared, "pigeonhole")),
  });

  it("widens from ratings to users to users and movies, at the defaults and three corners", () => {
    for (const [users, shared] of [[60, 0.7], [20, 0], [80, 0], [80, 0.95]]) {
      const w = widths(users, shared);
      expect(w.user).toBeGreaterThan(w.row);
      expect(w.pigeonhole).toBeGreaterThan(w.user);
    }
  });

  it("lets pairing cancel the user error when 20 users share 0.95 of it", () => {
    const w = widths(20, 0.95);
    expect(w.user).toBeLessThan(w.row);
    expect(w.pigeonhole).toBeGreaterThan(w.user);
  });

  it("settles its user-clustered endpoints as replicates grow into the thousands", () => {
    const values = differences(60, 0.7, "user");
    const ends = (b) => [
      percentile(values.slice(0, b), 0.025),
      percentile(values.slice(0, b), 0.975),
    ];
    const [low, high] = ends(2000);
    const drift = (b) => {
      const [l, h] = ends(b);
      return Math.abs(l - low) + Math.abs(h - high);
    };
    expect(drift(1000)).toBeLessThan(drift(100));
  });
});
