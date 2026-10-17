import { describe, expect, it } from "vitest";
import {
  euclidean,
  gower,
  histogram,
  kdNearest,
  kdTree,
  manhattan,
  nearest,
  predict,
  relativeContrast,
} from "./knn.js";
import { leastSquares } from "./linalg.js";
import { rmse } from "./metrics.js";
import { cumulative, covariance, jacobi, pca } from "./pca.js";
import { mulberry32, normal } from "./random.js";
import { wideRatings } from "./ratings.js";
import { oneStandardError } from "./tuning.js";

const cloud = (seed, n, d) => {
  const rng = mulberry32(seed);
  return Array.from({ length: n }, () => Array.from({ length: d }, () => rng()));
};

describe("nearest neighbours", () => {
  const points = cloud(1, 400, 3);
  const query = [0.5, 0.5, 0.5];

  it("returns the k closest rows in order of distance", () => {
    const found = nearest(points, query, 7, euclidean);
    expect(found).toHaveLength(7);
    const all = points.map((p) => euclidean(p, query)).sort((a, b) => a - b);
    found.forEach((hit, rank) => expect(hit.distance).toBeCloseTo(all[rank], 12));
  });

  it("predicts the mean rating of those neighbours", () => {
    const ratings = points.map((_, index) => (index % 5) + 1);
    const found = nearest(points, query, 9, manhattan);
    const mean = found.reduce((s, hit) => s + ratings[hit.index], 0) / 9;
    expect(predict(points, ratings, query, 9, manhattan)).toBeCloseTo(mean, 12);
  });

  it("finds exactly what brute force finds with a k-d tree, visiting fewer rows", () => {
    const tree = kdTree(points);
    for (const target of cloud(2, 20, 3)) {
      const { neighbours, visited } = kdNearest(tree, points, target, 5);
      const brute = nearest(points, target, 5, euclidean);
      expect(neighbours.map((hit) => hit.index)).toEqual(brute.map((hit) => hit.index));
      expect(visited).toBeLessThan(points.length);
    }
  });

  it("keeps Manhattan at or above Euclidean, and Gower within [0, 1]", () => {
    const [a, b] = points;
    expect(manhattan(a, b)).toBeGreaterThanOrEqual(euclidean(a, b));
    const distance = gower([1, 1, 1], [3]);
    expect(distance([0, 0, 0, 0], [1, 1, 1, 1])).toBe(1);
    expect(distance([0, 0, 0, 0], [0, 0, 0, 1])).toBeCloseTo(0.25, 12);
  });

  it("concentrates distances as the dimension grows", () => {
    const contrast = (d) => relativeContrast(cloud(3, 500, d), Array(d).fill(0.5), euclidean);
    expect(contrast(100)).toBeLessThan(contrast(2) / 10);
  });

  it("bins every value once", () => {
    const bins = histogram([0.1, 0.2, 0.9, 1.0], 0, 1, 4);
    expect(bins.reduce((s, bin) => s + bin.count, 0)).toBe(4);
  });
});

describe("principal components", () => {
  it("diagonalises a symmetric matrix into orthonormal eigenvectors", () => {
    const rng = mulberry32(4);
    const xs = Array.from({ length: 200 }, () => {
      const z = normal(rng);
      return [z + 0.3 * normal(rng), z + 0.3 * normal(rng), normal(rng), 2 * normal(rng)];
    });
    const cov = covariance(xs);
    const { values, vectors } = jacobi(cov);
    vectors.forEach((v, k) => {
      const av = cov.map((row) => row.reduce((s, c, j) => s + c * v[j], 0));
      av.forEach((value, i) => expect(value).toBeCloseTo(values[k] * v[i], 9));
      vectors.forEach((w, l) => {
        const inner = v.reduce((s, x, j) => s + x * w[j], 0);
        expect(inner).toBeCloseTo(k === l ? 1 : 0, 9);
      });
    });
    const trace = cov.reduce((s, row, i) => s + row[i], 0);
    expect(values.reduce((s, v) => s + v, 0)).toBeCloseTo(trace, 9);
    for (let k = 1; k < values.length; k += 1) {
      expect(values[k]).toBeLessThanOrEqual(values[k - 1]);
    }
  });

  it("gives uncorrelated scores whose variances are the eigenvalues", () => {
    const rows = wideRatings({ n: 400 }).map((row) => row.features);
    const fitted = pca(rows);
    const scores = rows.map((row) => fitted.project(row, 3));
    const cov = covariance(scores);
    expect(cov[0][1]).toBeCloseTo(0, 9);
    expect(cov[0][0]).toBeCloseTo(fitted.values[0], 9);
    expect(cumulative(fitted.values).at(-1)).toBeCloseTo(1, 12);
  });

  it("lets a large-unit column dominate the first component unless scaled", () => {
    const rows = wideRatings({ n: 400 }).map((row) => row.features);
    const raw = pca(rows, { scale: false });
    const scaled = pca(rows);
    expect(Math.abs(raw.vectors[0][10])).toBeGreaterThan(0.99);
    expect(Math.abs(scaled.vectors[0][10])).toBeLessThan(0.5);
  });

  it("finds a planted low-variance signal only once the last component is kept", () => {
    const rows = wideRatings({ n: 300, planted: true });
    const [train, later] = [rows.slice(0, 240), rows.slice(240)];
    const fitted = pca(train.map((row) => row.features));
    const score = (m) => {
      const design = (row) => [1, ...fitted.project(row.features, m)];
      const coef = leastSquares(train.map(design), train.map((row) => row.rating));
      const guesses = later.map((row) => design(row).reduce((s, x, j) => s + x * coef[j], 0));
      return rmse(guesses, later.map((row) => row.rating));
    };
    expect(score(11)).toBeLessThan(score(10) - 0.05);
  });

  it("can prefer the fewest components within one standard error", () => {
    const points = [1, 2, 3, 4].map((count, index) => ({
      lambda: count,
      error: [1.0, 0.82, 0.8, 0.81][index],
      se: 0.05,
    }));
    const { simplest } = oneStandardError(points, (a, b) => a.lambda < b.lambda);
    expect(simplest.lambda).toBe(2);
  });
});
