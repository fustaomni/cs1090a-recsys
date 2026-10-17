import { describe, expect, it } from "vitest";
import {
  blockSurface,
  ensemblePredict,
  forest,
  outOfBag,
  splitFrequency,
  varianceAcrossDatasets,
} from "./ensemble.js";
import { forestRatings } from "./ratings.js";
import { grow, view } from "./tree.js";

const FEATURES = ["user", "film", "genre", "noise"];
const rows = forestRatings({ n: 200 });
const queries = forestRatings({ seed: 7, n: 30 });

describe("bagging", () => {
  const members = forest(rows, FEATURES, { trees: 20, seed: 3 });

  it("leaves about 36.8% of rows out of each bootstrap sample", () => {
    const big = forest(forestRatings({ n: 1000 }), ["user"], { trees: 5, minLeaf: 50, seed: 4 });
    for (const member of big) expect(1 - member.inBag.size / 1000).toBeCloseTo(Math.exp(-1), 1);
  });

  it("predicts the mean of its trees", () => {
    const row = queries[0];
    const mean = members.reduce((s, m) => s + m.model.predict(row), 0) / members.length;
    expect(ensemblePredict(members, row)).toBeCloseTo(mean, 12);
  });

  it("predicts each training row out of bag only with trees that never saw it", () => {
    const oob = outOfBag(members, rows);
    const i = rows.findIndex((_, index) => members.some((m) => !m.inBag.has(index)));
    const outside = members.filter((m) => !m.inBag.has(i));
    const mean = outside.reduce((s, m) => s + m.model.predict(rows[i]), 0) / outside.length;
    expect(oob[i]).toBeCloseTo(mean, 12);
  });

  it("lowers variance across datasets toward a floor above zero", () => {
    const result = varianceAcrossDatasets(
      (seed) => forestRatings({ seed, n: 150 }),
      FEATURES,
      queries.slice(0, 12),
      { datasets: 5, trees: 15 },
    );
    expect(result.perB.at(-1)).toBeLessThan(result.perB[0]);
    expect(result.rho).toBeGreaterThan(0);
    expect(result.rho).toBeLessThan(1);
  });
});

describe("random forests", () => {
  it("grow exactly the plain tree when every feature is allowed at every split", () => {
    const plain = view(grow(rows, FEATURES, { minLeaf: 3 }));
    const same = view(grow(rows, FEATURES, { minLeaf: 3, mtry: 4, rng: () => 0.5 }));
    for (const row of queries) expect(same.predict(row)).toBe(plain.predict(row));
  });

  it("decorrelate their trees when each split sees fewer features", () => {
    const rho = (mtry) =>
      varianceAcrossDatasets((seed) => forestRatings({ seed, n: 200 }), FEATURES, queries, {
        datasets: 8,
        trees: 20,
        mtry,
      }).rho;
    expect(rho(1)).toBeLessThan(rho(4));
  });

  it("spread their root splits across features when mtry is small", () => {
    const bagged = splitFrequency(forest(rows, FEATURES, { trees: 30, seed: 6 }), FEATURES, 1)[0];
    const random = splitFrequency(
      forest(rows, FEATURES, { trees: 30, mtry: 1, seed: 6 }),
      FEATURES,
      1,
    )[0];
    expect(Math.max(...random)).toBeLessThan(Math.max(...bagged));
  });
});

describe("drawing an average of trees", () => {
  it("keeps every cell flat with vertical walls between cells", () => {
    const surface = blockSurface((row) => row.user, "user", "film", [0, 1], [0, 1], 2, {});
    expect(surface.x).toEqual([0, 0.5, 0.5, 1]);
    expect(surface.z[0]).toEqual([0.25, 0.25, 0.75, 0.75]);
  });
});
