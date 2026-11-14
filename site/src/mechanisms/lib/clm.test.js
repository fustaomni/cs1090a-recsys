import { describe, expect, it } from "vitest";
import { clmFit, logLikelihood, ordinalRatings } from "./ordinal.js";

// Model 14's fifty ratings: ordinalRatings({ seed: 141 }), fitted with the page's settings.
const rows = ordinalRatings({ seed: 141 });
const fit = clmFit(rows);

describe("the cumulative link model, as Model 14 shows it", () => {
  it("reaches the maximum likelihood on its fifty ratings", () => {
    const longer = clmFit(rows, { iterations: 30000 });
    expect(rows).toHaveLength(50);
    expect(logLikelihood(rows, longer) - logLikelihood(rows, fit)).toBeLessThan(1e-3);
  });

  it("learns cut-points that are not equally spaced", () => {
    const gaps = fit.cuts.slice(1).map((cut, index) => cut - fit.cuts[index]);
    expect(gaps).toHaveLength(3);
    expect(Math.max(...gaps) - Math.min(...gaps)).toBeGreaterThan(0.1);
  });
});
