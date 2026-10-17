// Stacking: a meta-learner weights the base models' out-of-fold predictions. The intercept is
// never penalised, so the predictions are centred first and the weights solve
//   minimise  (1/2n)||y_c - P_c w||^2 + (lambda/2)||w||^2
// optionally with w >= 0 (non-negative least squares or non-negative ridge) and optionally
// with the weights summing to one. With a handful of base models the constrained problem is
// solved exactly by checking every set of free weights against the KKT conditions.

import { leastSquares } from "./linalg.js";

function centred(predictions, ys) {
  const n = ys.length;
  const p = predictions[0].length;
  const ybar = ys.reduce((s, y) => s + y, 0) / n;
  const pbar = Array.from({ length: p }, (_, j) =>
    predictions.reduce((total, row) => total + row[j], 0) / n,
  );
  const gram = Array.from({ length: p }, () => new Array(p).fill(0));
  const cross = new Array(p).fill(0);
  predictions.forEach((row, i) => {
    for (let a = 0; a < p; a += 1) {
      cross[a] += ((row[a] - pbar[a]) * (ys[i] - ybar)) / n;
      for (let b = 0; b < p; b += 1) {
        gram[a][b] += ((row[a] - pbar[a]) * (row[b] - pbar[b])) / n;
      }
    }
  });
  return { ybar, pbar, gram, cross };
}

export function metaObjective({ gram, cross }, w, lambda) {
  let value = 0;
  for (let a = 0; a < w.length; a += 1) {
    value -= cross[a] * w[a];
    for (let b = 0; b < w.length; b += 1) value += 0.5 * w[a] * gram[a][b] * w[b];
    value += 0.5 * lambda * w[a] * w[a];
  }
  return value;
}

function solveFree(stats, free, lambda, sumToOne) {
  const { gram, cross } = stats;
  const k = free.length;
  const rows = free.map((a, i) =>
    free.map((b, j) => gram[a][b] + (i === j ? lambda : 0)).concat(sumToOne ? [1] : []),
  );
  const rhs = free.map((a) => cross[a]);
  if (sumToOne) {
    rows.push(new Array(k).fill(1).concat([0]));
    rhs.push(1);
  }
  const solution = leastSquares(rows, rhs);
  return solution.slice(0, k);
}

export function metaFit(predictions, ys, options = {}) {
  const { method = "ridge", lambda = 0, sumToOne = false } = options;
  const stats = centred(predictions, ys);
  const p = stats.cross.length;
  const penalty = method === "ols" || method === "nnls" ? 0 : lambda;
  const nonNegative = method !== "ols";
  const all = Array.from({ length: p }, (_, j) => j);
  const unconstrained = new Array(p).fill(0);
  solveFree(stats, all, penalty, sumToOne).forEach((v, i) => {
    unconstrained[all[i]] = v;
  });
  let best = { w: unconstrained, value: metaObjective(stats, unconstrained, penalty) };
  if (nonNegative && unconstrained.some((v) => v < 0)) {
    best = null;
    for (let mask = 1; mask < 1 << p; mask += 1) {
      const free = all.filter((j) => mask & (1 << j));
      if (sumToOne === false && free.length === 0) continue;
      let values;
      try {
        values = solveFree(stats, free, penalty, sumToOne);
      } catch {
        continue;
      }
      if (values.some((v) => v < -1e-12)) continue;
      const w = new Array(p).fill(0);
      free.forEach((j, i) => {
        w[j] = Math.max(0, values[i]);
      });
      const value = metaObjective(stats, w, penalty);
      if (!best || value < best.value - 1e-15) best = { w, value };
    }
    if (!best && !sumToOne) best = { w: new Array(p).fill(0), value: 0 };
  }
  const w = best.w;
  const intercept = stats.ybar - stats.pbar.reduce((s, m, j) => s + m * w[j], 0);
  const binding = w.map((v, j) => nonNegative && v === 0 && unconstrained[j] < 0);
  return {
    w,
    intercept,
    unconstrained,
    binding,
    stats,
    predict: (row) => intercept + row.reduce((s, v, j) => s + v * w[j], 0),
  };
}

// Krogh and Vedelsby: for weights summing to one and squared error,
// ensemble error = weighted average member error - weighted ambiguity.
export function ambiguity(predictions, ys, weights) {
  const n = ys.length;
  let member = 0;
  let spread = 0;
  let ensemble = 0;
  predictions.forEach((row, i) => {
    const combined = row.reduce((s, v, j) => s + v * weights[j], 0);
    row.forEach((v, j) => {
      member += (weights[j] * (v - ys[i]) ** 2) / n;
      spread += (weights[j] * (v - combined) ** 2) / n;
    });
    ensemble += (combined - ys[i]) ** 2 / n;
  });
  return { member, spread, ensemble };
}

export function correlation(xs, ys) {
  const n = xs.length;
  const mx = xs.reduce((s, v) => s + v, 0) / n;
  const my = ys.reduce((s, v) => s + v, 0) / n;
  let sxy = 0;
  let sxx = 0;
  let syy = 0;
  for (let i = 0; i < n; i += 1) {
    sxy += (xs[i] - mx) * (ys[i] - my);
    sxx += (xs[i] - mx) ** 2;
    syy += (ys[i] - my) ** 2;
  }
  return sxy / Math.sqrt(sxx * syy);
}
