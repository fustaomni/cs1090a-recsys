// Ridge and lasso on standardised predictors, in the scaling glmnet uses:
//   ridge  (1/2n)||y - Xb||^2 + (lambda/2)||b||^2
//   lasso  (1/2n)||y - Xb||^2 + lambda ||b||_1
// The intercept is the mean rating and is never penalised.

import { mean } from "./stats.js";

export function standardiser(rows, keys) {
  const centre = {};
  const scale = {};
  for (const key of keys) {
    const values = rows.map((row) => row[key]);
    centre[key] = mean(values);
    scale[key] = Math.sqrt(mean(values.map((v) => (v - centre[key]) ** 2)));
  }
  return (row) => keys.map((key) => (row[key] - centre[key]) / scale[key]);
}

// Standardised predictors and centred ratings, with the scaling fitted on these rows only, so
// that a fold's validation rows are transformed by what the fold's training rows learned.
export function prepared(rows, keys) {
  const standard = standardiser(rows, keys);
  const ybar = mean(rows.map((row) => row.rating));
  return { standard, ybar, xs: rows.map(standard), ys: rows.map((row) => row.rating - ybar) };
}

export function moments(xs, ys) {
  const n = xs.length;
  const p = xs[0].length;
  const gram = Array.from({ length: p }, () => new Array(p).fill(0));
  const cross = new Array(p).fill(0);
  xs.forEach((x, row) => {
    for (let i = 0; i < p; i += 1) {
      cross[i] += (x[i] * ys[row]) / n;
      for (let j = 0; j < p; j += 1) gram[i][j] += (x[i] * x[j]) / n;
    }
  });
  return { gram, cross };
}

// Solves (G + lambda I) b = c by Cholesky; G + lambda I is positive definite for lambda > 0
// and for lambda = 0 whenever the predictors are not collinear.
export function ridge({ gram, cross }, lambda) {
  const p = cross.length;
  const a = gram.map((row, i) => row.map((value, j) => value + (i === j ? lambda : 0)));
  const l = Array.from({ length: p }, () => new Array(p).fill(0));
  for (let i = 0; i < p; i += 1) {
    for (let j = 0; j <= i; j += 1) {
      let sum = a[i][j];
      for (let k = 0; k < j; k += 1) sum -= l[i][k] * l[j][k];
      l[i][j] = i === j ? Math.sqrt(sum) : sum / l[j][j];
    }
  }
  const z = new Array(p).fill(0);
  for (let i = 0; i < p; i += 1) {
    let sum = cross[i];
    for (let k = 0; k < i; k += 1) sum -= l[i][k] * z[k];
    z[i] = sum / l[i][i];
  }
  const b = new Array(p).fill(0);
  for (let i = p - 1; i >= 0; i -= 1) {
    let sum = z[i];
    for (let k = i + 1; k < p; k += 1) sum -= l[k][i] * b[k];
    b[i] = sum / l[i][i];
  }
  return b;
}

// Eigenvalues of a symmetric 2 x 2 matrix: the squared singular values of X, over n.
export function eigen2([[a, b], [, d]]) {
  const half = (a + d) / 2;
  const gap = Math.sqrt(((a - d) / 2) ** 2 + b * b);
  return [half + gap, half - gap];
}

export function softThreshold(z, lambda) {
  return Math.sign(z) * Math.max(Math.abs(z) - lambda, 0);
}

export function lambdaMax(xs, ys) {
  const { cross } = moments(xs, ys);
  return Math.max(...cross.map(Math.abs));
}

// Cyclic coordinate descent from zero. Each update sets b_j = S(z_j, lambda) with
// z_j = b_j + x_j'r / n, and every update is recorded so the path can be replayed.
export function lasso(xs, ys, lambda, { passes = 200, tolerance = 1e-9 } = {}) {
  const n = xs.length;
  const p = xs[0].length;
  const scale = Array.from({ length: p }, (_, j) => xs.reduce((s, x) => s + x[j] ** 2, 0) / n);
  const coef = new Array(p).fill(0);
  const residual = ys.slice();
  const trace = [coef.slice()];
  for (let pass = 0; pass < passes; pass += 1) {
    let largest = 0;
    for (let j = 0; j < p; j += 1) {
      let inner = 0;
      for (let row = 0; row < n; row += 1) inner += xs[row][j] * residual[row];
      const z = coef[j] * scale[j] + inner / n;
      const next = softThreshold(z, lambda) / scale[j];
      const change = next - coef[j];
      if (change !== 0) {
        for (let row = 0; row < n; row += 1) residual[row] -= change * xs[row][j];
        coef[j] = next;
        largest = Math.max(largest, Math.abs(change));
      }
      trace.push(coef.slice());
    }
    if (largest < tolerance) break;
  }
  return { coef, trace };
}

// KKT: |x_j'r|/n equals lambda where b_j is non-zero and is at most lambda where b_j is zero.
export function kkt(xs, ys, coef, lambda) {
  const n = xs.length;
  const residual = ys.map((y, row) => y - xs[row].reduce((s, x, j) => s + x * coef[j], 0));
  return coef.map((b, j) => {
    const gradient = xs.reduce((s, x, row) => s + x[j] * residual[row], 0) / n;
    const holds =
      b === 0
        ? Math.abs(gradient) <= lambda + 1e-6
        : Math.abs(gradient - Math.sign(b) * lambda) <= 1e-6;
    return { gradient, holds };
  });
}
