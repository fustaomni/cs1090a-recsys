import { describe, expect, it } from "vitest";
import { ensemblePredict } from "./ensemble.js";
import { rmseOf } from "./importance.js";
import { estimates, oobRmse } from "./oob.js";
import { driftRatings } from "./ratings.js";

// Technique 7's data: driftRatings({ seed: 111, n: 300 }), the first 240 training, six seeds.
const rows = driftRatings({ seed: 111, n: 300 });
const train = rows.slice(0, 240);
const later = rows.slice(240);
const runs = [1, 2, 3, 4, 5, 6].map((seed) => estimates(train, later, seed));
const mean = (values) => values.reduce((s, v) => s + v, 0) / values.length;

describe("out-of-bag error, as Technique 7 shows it", () => {
  it("scores the temporal forest on the same held-out later rows as the within-period one", () => {
    for (const run of runs) {
      const held = run.held.map((i) => later[i]);
      expect(held).toHaveLength(30);
      const past = (row) => ensemblePredict(run.members, row);
      expect(run.temporalHeld).toBeCloseTo(rmseOf(past, held), 12);
    }
  });

  it("agrees closely with random cross-validation, both ignoring time", () => {
    for (const run of runs) expect(Math.abs(run.values[0] - run.values[1])).toBeLessThan(0.06);
  });

  it("starts higher with few trees and settles as B grows", () => {
    const { members } = runs[0];
    expect(oobRmse(members, train, 1)).toBeGreaterThan(oobRmse(members, train, 30));
  });

  it("finds the later period easier to predict on these drifting ratings", () => {
    expect(mean(runs.map((run) => run.values[2] - run.values[0]))).toBeLessThan(0);
  });
});
