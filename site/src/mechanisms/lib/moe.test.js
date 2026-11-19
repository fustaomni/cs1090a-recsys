import { describe, expect, it } from "vitest";
import {
  bucketOf,
  bucketReport,
  gateFeatures,
  mix,
  pooledRmse,
  softmax,
  usable,
} from "./moe.js";

describe("the softmax gate", () => {
  it("turns the scores 4.2, 1.1 and -2.5 into weights of about 95.6%, 4.3% and 0.1%", () => {
    const weights = softmax([4.2, 1.1, -2.5]);
    expect(weights).toHaveLength(3);
    expect(weights[0]).toBeCloseTo(0.9558, 3);
    expect(weights[1]).toBeCloseTo(0.0431, 3);
    expect(weights[2]).toBeCloseTo(0.0012, 3);
    expect(weights.reduce((sum, weight) => sum + weight, 0)).toBeCloseTo(1, 12);
  });

  it("stays finite past exp's range, because it subtracts the largest score first", () => {
    const weights = softmax([1000, 0]);
    expect(weights[0]).toBeCloseTo(1, 12);
    expect(weights[1]).toBeCloseTo(0, 12);
  });

  it("gives equal scores equal weights", () => {
    expect(softmax([2, 2])).toEqual([0.5, 0.5]);
  });
});

describe("mixing the experts", () => {
  it("weights each expert's prediction by its gate weight", () => {
    expect(mix([3, 4], [0.25, 0.75])).toBeCloseTo(3.75, 12);
  });

  it("refuses predictions and weights of different lengths", () => {
    expect(() => mix([3, 4], [1])).toThrow();
  });
});

describe("the leakage guard", () => {
  const rows = [
    { user: 0, movie: 0, time: 9, rating: 4 },
    { user: 0, movie: 1, time: 10, rating: 3 },
    { user: 1, movie: 0, time: 11, rating: 5 },
  ];

  it("keeps a rating strictly before the request and blocks one at the same second", () => {
    const { before, blocked } = usable(rows, 10);
    expect(before.map((row) => row.time)).toEqual([9]);
    expect(blocked.map((row) => row.time)).toEqual([10, 11]);
  });

  it("counts the user's and the movie's training ratings as the gate's two features", () => {
    const training = [
      { user: 0, movie: 0, time: 1 },
      { user: 0, movie: 1, time: 2 },
      { user: 1, movie: 0, time: 3 },
    ];
    expect(gateFeatures(training, { user: 0, movie: 0 }, 5)).toEqual({
      userCount: 2,
      movieCount: 2,
    });
  });

  it("refuses training that holds a rating at or after the boundary", () => {
    expect(() => gateFeatures(rows, { user: 0, movie: 0 }, 10)).toThrow(/leak/i);
  });
});

describe("buckets by training history", () => {
  it.each([
    [{ userCount: 3, movieCount: 2 }, "warm"],
    [{ userCount: 0, movieCount: 2 }, "new user"],
    [{ userCount: 3, movieCount: 0 }, "new movie"],
    [{ userCount: 0, movieCount: 0 }, "both new"],
  ])("puts %o in the %s bucket", (features, bucket) => {
    expect(bucketOf(features)).toBe(bucket);
  });
});

describe("per-bucket RMSE", () => {
  const scored = [
    { user: 0, bucket: "warm", prediction: 4, rating: 3 },
    { user: 1, bucket: "warm", prediction: 4, rating: 5 },
    { user: 2, bucket: "warm", prediction: 2, rating: 3 },
    { user: 3, bucket: "new user", prediction: 1, rating: 4 },
  ];
  const options = { minimum: 2, draws: 200, seed: 7 };

  it("pools every error, rather than averaging the buckets' RMSEs", () => {
    expect(pooledRmse(scored)).toBeCloseTo(Math.sqrt(3), 12);
    expect(pooledRmse(scored)).not.toBeCloseTo(2, 3);
  });

  it("gives each bucket its count and RMSE, and flags one too small to trust", () => {
    const report = bucketReport(scored, options);
    expect(report.warm).toMatchObject({ n: 3, small: false });
    expect(report.warm.rmse).toBeCloseTo(1, 12);
    expect(report["new user"]).toMatchObject({ n: 1, small: true });
    expect(report["new user"].rmse).toBeCloseTo(3, 12);
  });

  it("brackets each bucket's RMSE with a seeded bootstrap interval", () => {
    const report = bucketReport(scored, options);
    expect(report.warm.low).toBeLessThanOrEqual(report.warm.rmse);
    expect(report.warm.high).toBeGreaterThanOrEqual(report.warm.rmse);
    expect(bucketReport(scored, options)).toEqual(report);
  });
});
