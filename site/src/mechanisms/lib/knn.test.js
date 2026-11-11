import { describe, expect, it } from "vitest";
import { euclidean, gower, kdNearest, kdTree, nearest } from "./knn.js";
import { mulberry32 } from "./random.js";

const cloud = (seed, n, d) => {
  const rng = mulberry32(seed);
  return Array.from({ length: n }, () => Array.from({ length: d }, () => rng()));
};

describe("kNN, as Model 6 shows it", () => {
  const points = cloud(11, 240, 3);
  const query = [0.5, 0.5, 0.5];

  it("draws a neighbourhood holding exactly the k nearest rows, its radius growing with k", () => {
    let previous = 0;
    for (const k of [1, 5, 10, 20, 40]) {
      const found = nearest(points, query, k, euclidean);
      const radius = found[k - 1].distance;
      const inside = points.filter((point) => euclidean(point, query) <= radius);
      expect(inside).toHaveLength(k);
      expect(radius).toBeGreaterThanOrEqual(previous);
      previous = radius;
    }
  });

  it("charges a row in another group a quarter of the Gower distance for that alone", () => {
    const distance = gower([1, 1, 1], [3]);
    expect(distance([0.2, 0.2, 0.2, 0], [0.2, 0.2, 0.2, 1])).toBeCloseTo(0.25, 12);
    expect(distance([0.2, 0.2, 0.2, 0], [0.2, 0.2, 0.2, 0])).toBe(0);
  });

  it("loses the k-d tree's advantage as the dimension grows", () => {
    const share = (d) => {
      const data = cloud(13, 400, d);
      const tree = kdTree(data);
      const queries = cloud(14, 20, d);
      const visited = queries.reduce((s, q) => s + kdNearest(tree, data, q, 10).visited, 0);
      return visited / (queries.length * data.length);
    };
    expect(share(20)).toBeGreaterThan(2 * share(3));
  });
});
