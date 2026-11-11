import { describe, expect, it } from "vitest";
import { adaBoostR2, weightedMedian } from "./boosting.js";
import { forestRatings } from "./ratings.js";

// Model 10's data and settings: the first 200 of forestRatings({ seed: 131, n: 260 }), seed 7.
const FEATURES = ["user", "movie"];
const OUTLIER = { user: 1.6, movie: 1.4, genre: 0, noise: 0, rating: 1 };
const clean = forestRatings({ seed: 131, n: 260 }).slice(0, 200);
const noisy = [...clean, OUTLIER];
const options = { rounds: 30, splits: 3, seed: 7 };

describe("AdaBoost.R2, as Model 10 shows it", () => {
  it("scales each tree's weight and every row's update by the learning rate", () => {
    const fit = adaBoostR2(clean, FEATURES, { ...options, learningRate: 0.5 });
    expect(fit.fitted.length).toBeGreaterThan(0);
    const first = fit.fitted[0];
    expect(first.weight).toBeCloseTo(0.5 * Math.log(1 / first.beta), 12);
    const raw = first.losses.map((l) => first.beta ** (0.5 * (1 - l)) / clean.length);
    const total = raw.reduce((s, w) => s + w, 0);
    first.weights.forEach((w, i) => expect(w).toBeCloseTo(raw[i] / total, 12));
  });

  it("lets one huge error set D and leave the outlier the heaviest row after a round", () => {
    const first = adaBoostR2(noisy, FEATURES, { ...options, loss: "linear" }).fitted[0];
    const last = noisy.length - 1;
    expect(first.losses[last]).toBe(1);
    expect(Math.max(...first.weights)).toBe(first.weights[last]);
  });

  it("lowers the average loss further under square and exponential losses", () => {
    const average = (loss) => adaBoostR2(noisy, FEATURES, { ...options, loss }).fitted[0].average;
    expect(average("square")).toBeLessThan(average("linear"));
    expect(average("exponential")).toBeLessThan(average("linear"));
  });

  it("lets the weighted median follow the outlier once enough tree weight chases it", () => {
    const fit = adaBoostR2(noisy, FEATURES, { ...options, loss: "linear" });
    expect(fit.fitted.length).toBeGreaterThan(0);
    const values = fit.fitted.map((step) => step.model.predict(OUTLIER));
    const weights = fit.fitted.map((step) => step.weight);
    const total = weights.reduce((s, w) => s + w, 0);
    const mean = values.reduce((s, v, k) => s + v * weights[k], 0) / total;
    const median = weightedMedian(values, weights);
    expect(Math.abs(median - OUTLIER.rating)).toBeLessThan(Math.abs(mean - OUTLIER.rating));
  });
});
