// Principal component analysis by the cyclic Jacobi method: plane rotations zero the
// off-diagonal entries of the symmetric covariance matrix until it is diagonal; the
// accumulated rotations are the orthonormal eigenvectors.

export function covariance(xs) {
  const n = xs.length;
  const p = xs[0].length;
  const cov = Array.from({ length: p }, () => new Array(p).fill(0));
  for (const x of xs) {
    for (let i = 0; i < p; i += 1) {
      for (let j = 0; j < p; j += 1) cov[i][j] += (x[i] * x[j]) / n;
    }
  }
  return cov;
}

export function jacobi(matrix, { sweeps = 60, tolerance = 1e-12 } = {}) {
  const p = matrix.length;
  const a = matrix.map((row) => row.slice());
  const v = Array.from({ length: p }, (_, i) => Array.from({ length: p }, (_, j) => +(i === j)));
  for (let sweep = 0; sweep < sweeps; sweep += 1) {
    let off = 0;
    for (let i = 0; i < p; i += 1) for (let j = i + 1; j < p; j += 1) off += a[i][j] ** 2;
    if (off < tolerance) break;
    for (let i = 0; i < p; i += 1) {
      for (let j = i + 1; j < p; j += 1) {
        if (Math.abs(a[i][j]) < 1e-300) continue;
        const theta = (a[j][j] - a[i][i]) / (2 * a[i][j]);
        const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;
        for (let k = 0; k < p; k += 1) {
          const aki = a[k][i];
          const akj = a[k][j];
          a[k][i] = c * aki - s * akj;
          a[k][j] = s * aki + c * akj;
        }
        for (let k = 0; k < p; k += 1) {
          const aik = a[i][k];
          const ajk = a[j][k];
          a[i][k] = c * aik - s * ajk;
          a[j][k] = s * aik + c * ajk;
        }
        for (let k = 0; k < p; k += 1) {
          const vki = v[k][i];
          const vkj = v[k][j];
          v[k][i] = c * vki - s * vkj;
          v[k][j] = s * vki + c * vkj;
        }
      }
    }
  }
  const order = a.map((row, i) => i).sort((x, y) => a[y][y] - a[x][x]);
  return {
    values: order.map((i) => a[i][i]),
    vectors: order.map((i) => v.map((row) => row[i])),
  };
}

// Fitted on training rows only: their centre, optionally their scale, and the components.
export function pca(rows, { scale = true } = {}) {
  const p = rows[0].length;
  const n = rows.length;
  const centre = Array.from({ length: p }, (_, j) => rows.reduce((s, r) => s + r[j], 0) / n);
  const spread = Array.from({ length: p }, (_, j) =>
    scale ? Math.sqrt(rows.reduce((s, r) => s + (r[j] - centre[j]) ** 2, 0) / n) : 1,
  );
  const prepare = (row) => row.map((value, j) => (value - centre[j]) / spread[j]);
  const { values, vectors } = jacobi(covariance(rows.map(prepare)));
  const project = (row, m) => {
    const x = prepare(row);
    return vectors.slice(0, m).map((vector) => vector.reduce((s, w, j) => s + w * x[j], 0));
  };
  return { values, vectors, project };
}

export function cumulative(values) {
  const total = values.reduce((s, v) => s + v, 0);
  let running = 0;
  return values.map((value) => {
    running += value;
    return running / total;
  });
}
