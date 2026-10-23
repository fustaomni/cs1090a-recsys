import { describe, expect, it } from "vitest";
import { mulberry32 } from "./random.js";
import { treeRatings } from "./ratings.js";
import {
  atAlpha,
  grow,
  impurityImportance,
  permutationImportance,
  pruningPath,
  splitCurve,
  stepSurface,
  view,
} from "./tree.js";

const FEATURES = ["user", "movie", "genre", "age"];
const rows = treeRatings({ n: 300 });
const ys = rows.map((row) => row.rating);
const tree = grow(rows, FEATURES, { minLeaf: 5 });

describe("growing a regression tree", () => {
  it("splits the root where the two sides' squared error is smallest, over every feature", () => {
    const brute = FEATURES.flatMap((feature) =>
      rows.flatMap((row) => {
        const t = row[feature];
        const left = ys.filter((_, i) => rows[i][feature] <= t);
        const right = ys.filter((_, i) => rows[i][feature] > t);
        if (left.length < 5 || right.length < 5) return [];
        const sse = (part) => {
          const mean = part.reduce((s, y) => s + y, 0) / part.length;
          return part.reduce((s, y) => s + (y - mean) ** 2, 0);
        };
        return [sse(left) + sse(right)];
      }),
    );
    expect(tree.root.split.sse).toBeCloseTo(Math.min(...brute), 9);
  });

  it("predicts a leaf mean, so every prediction stays within [1, 5]", () => {
    const full = view(tree);
    for (const row of rows) {
      const guess = full.predict(row);
      expect(guess).toBeGreaterThanOrEqual(1);
      expect(guess).toBeLessThanOrEqual(5);
    }
  });

  it("never raises training error as splits are added", () => {
    const sse = (steps) => {
      const current = view(tree, { steps });
      return rows.reduce((s, row, i) => s + (current.predict(row) - ys[i]) ** 2, 0);
    };
    for (const steps of [1, 2, 5, 10, 20]) expect(sse(steps)).toBeLessThanOrEqual(sse(steps - 1));
  });

  it("returns a split curve whose minimum is the chosen threshold", () => {
    const { feature, threshold } = tree.root.split;
    const curve = splitCurve(rows, ys, feature, 5);
    const lowest = curve.reduce((a, b) => (b.sse < a.sse ? b : a));
    expect(lowest.threshold).toBeCloseTo(threshold, 12);
  });
});

describe("cost-complexity pruning", () => {
  const path = pruningPath(tree);

  it("produces nested subtrees with rising alpha and falling leaf counts", () => {
    for (let k = 1; k < path.length; k += 1) {
      expect(path[k].alpha).toBeGreaterThanOrEqual(path[k - 1].alpha - 1e-12);
      expect(path[k].leaves).toBeLessThan(path[k - 1].leaves);
      for (const id of path[k - 1].collapsed) expect(path[k].collapsed.has(id)).toBe(true);
    }
    expect(path.at(-1).leaves).toBe(1);
  });

  it("chooses the subtree minimising SSE + alpha x leaves among the sequence", () => {
    const alpha = path[Math.floor(path.length / 2)].alpha * 1.01;
    const cost = (step) => {
      const current = view(tree, { collapsed: step.collapsed });
      const sse = rows.reduce((s, row, i) => s + (current.predict(row) - ys[i]) ** 2, 0);
      return sse + alpha * step.leaves;
    };
    const chosen = atAlpha(path, alpha);
    for (const step of path) expect(cost(chosen)).toBeLessThanOrEqual(cost(step) + 1e-9);
  });
});

describe("importance and drawing", () => {
  it("gives impurity shares that sum to one", () => {
    const shares = impurityImportance(tree, FEATURES);
    expect(shares.reduce((s, v) => s + v, 0)).toBeCloseTo(1, 12);
  });

  it("measures no permutation importance for a feature the model never uses", () => {
    const predict = (row) => (row.user > 3.6 ? 4 : 3);
    const [user, , genre] = permutationImportance(predict, rows, FEATURES, mulberry32(3), 5);
    expect(genre).toBe(0);
    expect(user).toBeGreaterThan(0);
  });

  it("draws a surface whose cells are flat between the split thresholds", () => {
    const predict = (row) => (row.user <= 3.6 ? 2 : 4);
    const surface = stepSurface(predict, "user", "movie", [2, 5], [2, 5], [
      { feature: "user", value: 3.6 },
    ], {});
    expect(surface.x).toEqual([2, 3.6, 3.6, 5]);
    expect(surface.z[0]).toEqual([2, 2, 4, 4]);
  });
});
