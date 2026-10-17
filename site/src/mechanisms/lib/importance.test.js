import { describe, expect, it } from "vitest";
import {
  outsideSupport,
  permutationRises,
  permuted,
  randomFolds,
  rmseOf,
  shares,
  shuffled,
  strata,
} from "./importance.js";
import { mulberry32 } from "./random.js";
import { forestRatings } from "./ratings.js";

const rows = forestRatings({ n: 200 });

describe("shuffling", () => {
  it("returns a permutation of the values", () => {
    const values = [1, 2, 3, 4, 5, 6];
    expect(shuffled(values, mulberry32(1)).sort()).toEqual(values);
  });

  it("keeps a conditional shuffle inside each stratum of the given feature", () => {
    const bins = strata(rows, "film", 5);
    const mixed = permuted(rows, "user", mulberry32(2), "film", 5);
    for (let b = 0; b < 5; b += 1) {
      const before = rows.filter((_, i) => bins[i] === b).map((row) => row.user).sort();
      const after = mixed.filter((_, i) => bins[i] === b).map((row) => row.user).sort();
      expect(after).toEqual(before);
    }
  });
});

describe("importance", () => {
  it("finds no rise for a feature the model never reads", () => {
    const predict = (row) => 3 + 0.5 * row.user;
    const rises = permutationRises(predict, rows, "noise", mulberry32(3), 5);
    expect(rises.every((rise) => rise === 0)).toBe(true);
    expect(permutationRises(predict, rows, "user", mulberry32(3), 5)[0]).toBeGreaterThan(0);
  });

  it("measures error as root mean squared error", () => {
    const one = [{ rating: 3 }, { rating: 5 }];
    expect(rmseOf(() => 4, one)).toBe(1);
  });

  it("turns rises into shares that sum to one, ignoring negatives", () => {
    const [first, second, third] = shares([0.3, 0.1, -0.05]);
    expect(first).toBeCloseTo(0.75, 12);
    expect(second).toBeCloseTo(0.25, 12);
    expect(third).toBe(0);
  });

  it("flags points far from every training point as outside the support", () => {
    const train = [{ user: 0, film: 0 }];
    const probe = [{ user: 0.1, film: 0 }, { user: 3, film: 3 }];
    expect(outsideSupport(train, probe, ["user", "film"], 1)).toBe(0.5);
  });

  it("partitions rows into random folds", () => {
    const folds = randomFolds(23, 5, mulberry32(4));
    expect(folds.flat().sort((a, b) => a - b)).toEqual(Array.from({ length: 23 }, (_, i) => i));
  });
});
