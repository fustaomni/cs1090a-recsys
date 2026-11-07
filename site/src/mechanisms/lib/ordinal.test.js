// site/src/mechanisms/lib/ordinal.test.js
import { describe, expect, it } from "vitest";
import { ORDINAL, bucket, clmFit, logLikelihood, ordinalRatings, score, start } from "./ordinal.js";

describe("ordinal regression, a cumulative link model (A.246)", () => {
  const large = ordinalRatings({ seed: 141, n: 2000 });
  const fit = clmFit(large);

  it("keeps its fitted cut-points in order", () => {
    for (let index = 1; index < fit.cuts.length; index += 1) {
      expect(fit.cuts[index]).toBeGreaterThan(fit.cuts[index - 1]);
    }
  });

  it("recovers the coefficients and cut-points it was generated from", () => {
    expect(fit.b1).toBeCloseTo(ORDINAL.user, 0);
    expect(fit.b2).toBeCloseTo(ORDINAL.movie, 0);
    fit.cuts.forEach((cut, index) => expect(Math.abs(cut - ORDINAL.cuts[index])).toBeLessThan(0.35));
  });

  it("raises the likelihood above its starting point", () => {
    expect(logLikelihood(large, fit)).toBeGreaterThan(logLikelihood(large, start()));
  });

  it("flips nothing at zero shift, and more ratings as the cut-offs move further", () => {
    const flips = (shift) =>
      large.filter((row) => bucket(score(fit, row), fit.cuts, shift) !== bucket(score(fit, row), fit.cuts)).length;
    expect(flips(0)).toBe(0);
    expect(flips(0.2)).toBeLessThan(flips(0.8));
  });
});
