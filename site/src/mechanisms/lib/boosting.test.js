import { describe, expect, it } from "vitest";
import { adaBoostR2, earlyStopping, gradientBoost, weightedMedian } from "./boosting.js";
import { forestRatings } from "./ratings.js";

const FEATURES = ["user", "film"];
const rows = forestRatings({ n: 200 });
const ys = rows.map((row) => row.rating);

describe("AdaBoost.R2", () => {
  const fit = adaBoostR2(rows, FEATURES, { rounds: 8, seed: 2 });

  it("takes the weighted median, not the mean", () => {
    expect(weightedMedian([1, 2, 10], [0.3, 0.4, 0.3])).toBe(2);
    expect(weightedMedian([1, 2, 10], [0.1, 0.1, 0.8])).toBe(10);
  });

  it("sets beta from the average loss and weights each tree by log(1 / beta)", () => {
    for (const step of fit.fitted) {
      expect(step.beta).toBeCloseTo(step.average / (1 - step.average), 12);
      expect(step.weight).toBeCloseTo(Math.log(1 / step.beta), 12);
      expect(step.weights.reduce((s, w) => s + w, 0)).toBeCloseTo(1, 12);
    }
  });

  it("shifts weight toward the rows the round predicted worst", () => {
    const first = fit.fitted[0];
    const worst = first.losses.indexOf(Math.max(...first.losses));
    const best = first.losses.indexOf(Math.min(...first.losses));
    expect(first.weights[worst] / first.weights[best]).toBeGreaterThan(1);
  });

  it("stops when the average loss reaches one half", () => {
    const noisy = rows.map((row, i) => ({ ...row, rating: i % 2 ? 1 : 5 }));
    const options = { rounds: 10, loss: "exponential", splits: 1, seed: 3 };
    const result = adaBoostR2(noisy, FEATURES, options);
    const last = result.history.at(-1);
    expect(last.stopped).toBe(true);
    expect(last.average).toBeGreaterThanOrEqual(0.5);
    for (const step of result.fitted) expect(step.average).toBeLessThan(0.5);
  });
});

describe("gradient boosting", () => {
  const fit = gradientBoost(rows, FEATURES, { stages: 20, learningRate: 0.3, splits: 4 });

  it("starts from the mean, so the first residuals sum to zero", () => {
    expect(fit.start).toBeCloseTo(ys.reduce((s, y) => s + y, 0) / ys.length, 12);
    expect(fit.steps[0].residuals.reduce((s, r) => s + r, 0)).toBeCloseTo(0, 9);
  });

  it("fits each stage to the residual y - F, the negative gradient of squared loss", () => {
    const second = fit.steps[1].residuals;
    rows.forEach((row, i) => {
      expect(second[i]).toBeCloseTo(row.rating - fit.predict(row, 1), 9);
    });
  });

  it("never raises training error from one stage to the next", () => {
    const sse = (count) =>
      rows.reduce((s, row) => s + (fit.predict(row, count) - row.rating) ** 2, 0);
    for (let count = 1; count <= 20; count += 1) {
      expect(sse(count)).toBeLessThanOrEqual(sse(count - 1) + 1e-9);
    }
  });

  it("starts from the median under absolute loss", () => {
    const robust = gradientBoost(rows, FEATURES, { stages: 2, loss: "absolute" });
    const sorted = ys.slice().sort((a, b) => a - b);
    expect(robust.start).toBe((sorted[99] + sorted[100]) / 2);
  });

  it("stops after the patience window and keeps the best stage", () => {
    const errors = [1.0, 0.9, 0.85, 0.86, 0.87, 0.84, 0.9, 0.91, 0.92];
    expect(earlyStopping(errors, 3)).toEqual({ best: 5, stoppedAt: 8 });
    expect(earlyStopping([1, 0.9, 0.95, 0.96, 0.97], 3)).toEqual({ best: 1, stoppedAt: 4 });
  });
});
