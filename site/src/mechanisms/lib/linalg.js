// Least squares by Householder QR, and the normal equations X'X b = X'y shown beside it.
// The solve uses QR because forming X'X squares the condition number, which matters exactly
// when uncentred polynomial terms make the columns nearly collinear.

export function leastSquares(rows, ys) {
  const n = rows.length;
  const p = rows[0].length;
  const a = rows.map((row) => row.slice());
  const b = ys.slice();
  for (let k = 0; k < p; k += 1) {
    let norm = 0;
    for (let i = k; i < n; i += 1) norm += a[i][k] ** 2;
    norm = Math.sqrt(norm);
    const alpha = a[k][k] > 0 ? -norm : norm;
    const v = new Array(n).fill(0);
    for (let i = k; i < n; i += 1) v[i] = a[i][k];
    v[k] -= alpha;
    let length = 0;
    for (let i = k; i < n; i += 1) length += v[i] * v[i];
    if (length === 0) continue;
    for (let j = k; j < p; j += 1) {
      let dot = 0;
      for (let i = k; i < n; i += 1) dot += v[i] * a[i][j];
      const scale = (2 * dot) / length;
      for (let i = k; i < n; i += 1) a[i][j] -= scale * v[i];
    }
    let dot = 0;
    for (let i = k; i < n; i += 1) dot += v[i] * b[i];
    const scale = (2 * dot) / length;
    for (let i = k; i < n; i += 1) b[i] -= scale * v[i];
  }
  const largest = Math.max(...a.slice(0, p).map((row, k) => Math.abs(row[k])));
  const coef = new Array(p).fill(0);
  for (let k = p - 1; k >= 0; k -= 1) {
    if (Math.abs(a[k][k]) <= 1e-12 * largest) {
      throw new Error(`column ${k} is a linear combination of the others`);
    }
    let sum = b[k];
    for (let j = k + 1; j < p; j += 1) sum -= a[k][j] * coef[j];
    coef[k] = sum / a[k][k];
  }
  return coef;
}

// X'X and X'y: the normal equations the solution satisfies.
export function normalEquations(rows, ys) {
  const p = rows[0].length;
  const gram = Array.from({ length: p }, () => new Array(p).fill(0));
  const moment = new Array(p).fill(0);
  rows.forEach((row, index) => {
    for (let i = 0; i < p; i += 1) {
      moment[i] += row[i] * ys[index];
      for (let j = 0; j < p; j += 1) gram[i][j] += row[i] * row[j];
    }
  });
  return { gram, moment };
}

export function dot(xs, ys) {
  return xs.reduce((total, x, index) => total + x * ys[index], 0);
}
