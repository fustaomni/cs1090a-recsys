import { describe, expect, it } from "vitest";
import { CROSSED, crossedFit, crossedRatings, kept } from "./crossed.js";

// Model 13's data: crossedRatings({ seed: 131 }), at its default pooling of 2.
const { rows } = crossedRatings({ seed: 131 });
const meanResidual = (fit, key, index) => {
  const other = key === "user" ? "movie" : "user";
  const offsets = key === "user" ? fit.movies : fit.users;
  const own = rows.filter((row) => row[key] === index);
  return own.reduce((s, row) => s + row.rating - fit.mu - offsets[row[other]], 0) / own.length;
};

describe("crossed offsets, as Model 13 shows them", () => {
  it("keeps n / (n + sigma^2 / tau^2) of each mean residual after the other offsets", () => {
    const fit = crossedFit(rows, { pooling: 2 });
    for (let u = 0; u < CROSSED.users; u += 1) {
      if (fit.userCount[u] === 0) continue;
      const share = kept(fit.userCount[u], 2) * meanResidual(fit, "user", u);
      expect(fit.users[u]).toBeCloseTo(share, 4);
    }
    for (let m = 0; m < CROSSED.movies; m += 1) {
      if (fit.movieCount[m] === 0) continue;
      const share = kept(fit.movieCount[m], 2) * meanResidual(fit, "movie", m);
      expect(fit.movies[m]).toBeCloseTo(share, 4);
    }
  });

  it("does not keep that share of the unpooled offset, since the other offsets move too", () => {
    const fit = crossedFit(rows, { pooling: 2 });
    const raw = crossedFit(rows, { pooling: 0 });
    const gaps = fit.users.map((b, u) => Math.abs(b - kept(fit.userCount[u], 2) * raw.users[u]));
    expect(Math.max(...gaps)).toBeGreaterThan(0.05);
  });
});
