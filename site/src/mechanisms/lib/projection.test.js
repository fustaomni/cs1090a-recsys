import { describe, expect, it } from "vitest";
import { euclidean, nearest } from "./knn.js";
import { rmse } from "./metrics.js";
import { pca } from "./pca.js";
import { wideRatings } from "./ratings.js";

// Technique 4's data: wideRatings({ seed: 81, n: 300 }), the first 240 rows training.
const TRAIN = 240;

function prepared(rows, scale) {
  const p = rows[0].length;
  const n = rows.length;
  const centre = Array.from({ length: p }, (_, j) => rows.reduce((s, r) => s + r[j], 0) / n);
  const spread = Array.from({ length: p }, (_, j) =>
    scale ? Math.sqrt(rows.reduce((s, r) => s + (r[j] - centre[j]) ** 2, 0) / n) : 1,
  );
  return (row) => row.map((value, j) => (value - centre[j]) / spread[j]);
}

function knnLater(rows, m) {
  const train = rows.slice(0, TRAIN);
  const later = rows.slice(TRAIN);
  const fitted = pca(train.map((row) => row.features));
  const points = train.map((row) => fitted.project(row.features, m));
  const guesses = later.map((row) => {
    const hits = nearest(points, fitted.project(row.features, m), 15, euclidean);
    return hits.reduce((s, hit) => s + train[hit.index].rating, 0) / hits.length;
  });
  return rmse(guesses, later.map((row) => row.rating));
}

describe("PCA, as Technique 4 shows it", () => {
  it("reproduces the prepared distances exactly when every component is kept, scaled or not", () => {
    const features = wideRatings({ seed: 81, n: 300 })
      .slice(0, TRAIN)
      .map((row) => row.features);
    const p = features[0].length;
    for (const scale of [true, false]) {
      const fitted = pca(features, { scale });
      const prepare = prepared(features, scale);
      for (const [a, b] of [[0, 1], [5, 40], [17, 200]]) {
        const rotated = euclidean(fitted.project(features[a], p), fitted.project(features[b], p));
        const original = euclidean(prepare(features[a]), prepare(features[b]));
        expect(Math.abs(rotated - original)).toBeLessThan(1e-6 * Math.max(1, original));
      }
    }
  });

  it("lets kNN barely change when the planted last component is added", () => {
    const rows = wideRatings({ seed: 81, n: 300, planted: true });
    const p = rows[0].features.length;
    expect(Math.abs(knnLater(rows, p) - knnLater(rows, p - 1))).toBeLessThan(0.05);
  });
});
