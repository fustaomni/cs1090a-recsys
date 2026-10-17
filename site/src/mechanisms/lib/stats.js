// Least squares for one predictor, written as the closed form a reader can check by hand.

export function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

export function covariance(xs, ys) {
  const xbar = mean(xs);
  const ybar = mean(ys);
  return xs.reduce((total, x, index) => total + (x - xbar) * (ys[index] - ybar), 0) / xs.length;
}

export function variance(xs) {
  return covariance(xs, xs);
}

// The fit on centred x: rating = b0 + b1 (x - xbar), so b0 is the mean rating.
export function simpleFit(xs, ys) {
  const slope = covariance(xs, ys) / variance(xs);
  return { b0: mean(ys), b1: slope, xbar: mean(xs) };
}

// The sufficient sums of the centred problem; SSE at any (b0, b1) then costs O(1).
export function sums(xs, ys) {
  const xbar = mean(xs);
  const centred = xs.map((x) => x - xbar);
  return {
    n: xs.length,
    sy: ys.reduce((total, y) => total + y, 0),
    syy: ys.reduce((total, y) => total + y * y, 0),
    sxx: centred.reduce((total, x) => total + x * x, 0),
    sxy: centred.reduce((total, x, index) => total + x * ys[index], 0),
  };
}

export function sse({ n, sy, syy, sxx, sxy }, b0, b1) {
  return syy - 2 * b0 * sy - 2 * b1 * sxy + n * b0 * b0 + b1 * b1 * sxx;
}
