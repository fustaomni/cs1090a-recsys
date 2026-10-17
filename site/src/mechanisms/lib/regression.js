import { leastSquares } from "./linalg.js";
import { mean } from "./stats.js";

// Linear models over named terms, each a function of one data row. Every model carries an
// intercept as its first coefficient.

export function design(rows, terms) {
  return rows.map((row) => [1, ...terms.map((term) => term.value(row))]);
}

export function fit(rows, terms, ys) {
  return leastSquares(design(rows, terms), ys);
}

export function predict(coef, terms, row) {
  const weighted = terms.map((term, index) => coef[index + 1] * term.value(row));
  return weighted.reduce((total, value) => total + value, coef[0]);
}

export function residuals(coef, terms, rows, ys) {
  return rows.map((row, index) => ys[index] - predict(coef, terms, row));
}

export function rSquared(observed, fitted) {
  const centre = mean(observed);
  const total = observed.reduce((sum, y) => sum + (y - centre) ** 2, 0);
  const left = observed.reduce((sum, y, index) => sum + (y - fitted[index]) ** 2, 0);
  return 1 - left / total;
}

// VIF_j = 1 / (1 - R_j^2), with R_j^2 from regressing term j on every other term.
export function vif(rows, terms) {
  if (terms.length < 2) return terms.map(() => 1);
  return terms.map((term, j) => {
    const others = terms.filter((_, k) => k !== j);
    const target = rows.map((row) => term.value(row));
    const coef = fit(rows, others, target);
    const fitted = rows.map((row) => predict(coef, others, row));
    return 1 / (1 - rSquared(target, fitted));
  });
}
