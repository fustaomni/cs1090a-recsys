// Encodings of a user's rating history. The smoothed mean S = (n ybar + m mu) / (n + m)
// shrinks a user with few ratings toward the global mean mu, and equals mu when n = 0. A
// naive mean includes the row's own rating, which leaks the target; a prior-only mean uses
// only that user's earlier ratings, the time-ordered form of out-of-fold encoding.

export function smoothed(n, ybar, m, mu) {
  return (n * ybar + m * mu) / (n + m);
}

// Each row's encoding, rows in time order: naive (all of the user's ratings in the window,
// including this one) or prior-only (strictly earlier ratings).
export function encodings(rows, m, mu) {
  const totals = new Map();
  const counts = new Map();
  for (const r of rows) {
    totals.set(r.user, (totals.get(r.user) ?? 0) + r.rating);
    counts.set(r.user, (counts.get(r.user) ?? 0) + 1);
  }
  const seenTotal = new Map();
  const seenCount = new Map();
  return rows.map((r) => {
    const n = seenCount.get(r.user) ?? 0;
    const sum = seenTotal.get(r.user) ?? 0;
    const prior = smoothed(n, n ? sum / n : mu, m, mu);
    const all = counts.get(r.user);
    const naive = smoothed(all, totals.get(r.user) / all, m, mu);
    seenCount.set(r.user, n + 1);
    seenTotal.set(r.user, sum + r.rating);
    return { naive, prior, earlier: n };
  });
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
