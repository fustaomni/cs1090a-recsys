// site/src/mechanisms/lib/coverage.js
// Technique 11, the prediction-interval coverage audit (A.246): split-conformal intervals,
// calibrated on held-out residuals, checked on test ratings for empirical against nominal
// coverage, overall and by user group, with their width and the interval score
// (upper - lower) + 2/alpha * distance outside the interval.
import { mulberry32, normal } from "./random.js";
import { toLevel } from "./ratings.js";

export const COVERAGE = { test: 30, calibration: 200, noise: { light: 1.1, heavy: 0.55 } };

function draw(rng, n) {
  const rows = [];
  for (let index = 0; index < n; index += 1) {
    const group = rng() < 0.5 ? "light" : "heavy";
    const center = Math.min(4.8, Math.max(1.2, 3.5 + 0.7 * normal(rng)));
    const rating = toLevel(center + COVERAGE.noise[group] * normal(rng));
    rows.push({ id: index + 1, group, center, rating });
  }
  return rows;
}

export function coverageData({ seed = 151, test = COVERAGE.test } = {}) {
  const rng = mulberry32(seed);
  const calibration = draw(rng, COVERAGE.calibration);
  return { calibration, test: draw(rng, test) };
}

export function conformalHalfWidth(calibration, level) {
  const residuals = calibration.map((row) => Math.abs(row.rating - row.center)).sort((a, b) => a - b);
  const rank = Math.ceil((residuals.length + 1) * level);
  return residuals[Math.min(rank, residuals.length) - 1];
}

export function intervalScore(lower, upper, observed, alpha) {
  const below = observed < lower ? (2 / alpha) * (lower - observed) : 0;
  const above = observed > upper ? (2 / alpha) * (observed - upper) : 0;
  return upper - lower + below + above;
}

export function audit(test, half, level) {
  const alpha = 1 - level;
  const rows = test.map((row) => {
    const lower = row.center - half;
    const upper = row.center + half;
    return {
      ...row,
      lower,
      upper,
      covered: row.rating >= lower && row.rating <= upper,
      score: intervalScore(lower, upper, row.rating, alpha),
    };
  });
  const share = (subset) => subset.filter((row) => row.covered).length / Math.max(subset.length, 1);
  const groups = ["light", "heavy"].map((group) => {
    const subset = rows.filter((row) => row.group === group);
    return { group, n: subset.length, coverage: share(subset) };
  });
  const mean = (values) => values.reduce((total, value) => total + value, 0) / values.length;
  return {
    rows,
    coverage: share(rows),
    groups,
    width: 2 * half,
    score: mean(rows.map((row) => row.score)),
  };
}
