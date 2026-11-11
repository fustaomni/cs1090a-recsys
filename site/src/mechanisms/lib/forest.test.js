import { describe, expect, it } from "vitest";
import { ensemblePredict, forest, varianceAcrossDatasets } from "./ensemble.js";
import { mulberry32 } from "./random.js";
import { forestRatings } from "./ratings.js";
import { impurityImportance, permutationImportance } from "./tree.js";

// Model 9's data and forest: forestRatings({ seed: 101, n: 240 }) split 200 and 40, seed 11.
const FEATURES = ["user", "movie", "genre", "noise"];
const rows = forestRatings({ seed: 101, n: 240 });
const train = rows.slice(0, 200);
const later = rows.slice(200);
const queries = forestRatings({ seed: 9, n: 20 });

describe("random forests, as Model 9 shows them", () => {
  it("lower the variance floor rho sigma squared when each split sees fewer features", () => {
    const floor = (mtry) =>
      varianceAcrossDatasets((seed) => forestRatings({ seed, n: 200 }), FEATURES, queries, {
        datasets: 8,
        trees: 20,
        mtry,
        minLeaf: 3,
      }).floor;
    expect(floor(1)).toBeLessThan(floor(4));
  });

  it("find single trees with one feature per split no worse on the later window", () => {
    const single = (mtry) => {
      const members = forest(train, FEATURES, { trees: 25, mtry, minLeaf: 3, seed: 11 });
      const errors = members.map((member) => {
        const squares = later.reduce((s, row) => s + (member.model.predict(row) - row.rating) ** 2, 0);
        return Math.sqrt(squares / later.length);
      });
      return errors.reduce((s, e) => s + e, 0) / errors.length;
    };
    expect(single(1)).toBeLessThanOrEqual(single(4));
  });

  it("credit the noise column by impurity on training data, far less by permutation later", () => {
    const members = forest(train, FEATURES, { trees: 40, mtry: 2, minLeaf: 3, seed: 11 });
    const impurity = members.reduce(
      (s, member) => s + impurityImportance(member.tree, FEATURES)[3] / members.length,
      0,
    );
    const predict = (row) => ensemblePredict(members, row);
    const raised = permutationImportance(predict, later, FEATURES, mulberry32(3), 10);
    const total = raised.reduce((s, v) => s + Math.max(v, 0), 0);
    expect(total).toBeGreaterThan(0);
    expect(impurity).toBeGreaterThan(0.03);
    expect(Math.max(raised[3], 0) / total).toBeLessThan(impurity / 2);
  });
});
