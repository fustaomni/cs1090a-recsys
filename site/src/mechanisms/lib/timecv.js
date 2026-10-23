// Time-aware cross-validation. Rows are sorted by timestamp; the training window ends at a
// quantile cutoff (T_val), and the folds subdivide only that window into blocks of equal row
// count, cut at timestamp boundaries so that ratings sharing a timestamp never straddle a
// train / validation edge.

export function byTime(rows) {
  return rows.slice().sort((a, b) => a.time - b.time);
}

// The first row index at or after the q quantile, moved forward past any tie.
export function cutAt(rows, q) {
  let index = Math.min(rows.length, Math.ceil(q * rows.length));
  while (index > 0 && index < rows.length && rows[index].time === rows[index - 1].time) {
    index += 1;
  }
  return index;
}

// Block edges of equal row count over rows[0 .. n), each moved to a timestamp boundary.
export function blockEdges(rows, n, blocks) {
  const edges = [0];
  for (let b = 1; b < blocks; b += 1) {
    let edge = Math.max(edges[b - 1] + 1, Math.round((n * b) / blocks));
    while (edge < n && rows[edge].time === rows[edge - 1].time) edge += 1;
    edges.push(Math.min(edge, n));
  }
  edges.push(n);
  return edges;
}

// Rolling-origin folds: fold k validates block k + 1 and trains on the blocks before it,
// all of them (expanding) or only the most recent `width` (sliding), dropping `gap` rows
// just before the validation block.
export function rollingFolds(edges, { sliding = false, width = 2, gap = 0 } = {}) {
  const span = (from, to) =>
    Array.from({ length: Math.max(0, to - from) }, (_, i) => from + i);
  return edges.slice(1, -1).map((start, k) => {
    const first = sliding ? edges[Math.max(0, k + 1 - width)] : 0;
    const trainEnd = Math.max(first, start - gap);
    return {
      train: span(first, trainEnd),
      gap: span(trainEnd, start),
      valid: span(start, edges[k + 2]),
    };
  });
}

// Shrunk user and movie offsets fitted on the given rows: mu + b_user + b_movie.
export function baseline(rows, shrink = 10) {
  const mu = rows.reduce((s, r) => s + r.rating, 0) / rows.length;
  const userSum = new Map();
  const userCount = new Map();
  for (const r of rows) {
    userSum.set(r.user, (userSum.get(r.user) ?? 0) + r.rating - mu);
    userCount.set(r.user, (userCount.get(r.user) ?? 0) + 1);
  }
  const bu = (user) => (userSum.get(user) ?? 0) / ((userCount.get(user) ?? 0) + shrink);
  const movieSum = new Map();
  const movieCount = new Map();
  for (const r of rows) {
    movieSum.set(r.movie, (movieSum.get(r.movie) ?? 0) + r.rating - mu - bu(r.user));
    movieCount.set(r.movie, (movieCount.get(r.movie) ?? 0) + 1);
  }
  const bi = (movie) => (movieSum.get(movie) ?? 0) / ((movieCount.get(movie) ?? 0) + shrink);
  return (row) => mu + bu(row.user) + bi(row.movie);
}

// Validation rows whose user statistics were fitted on a later rating by the same user: the
// row's feature includes its own future.
export function futureLeaks(trainRows, validRows) {
  const latest = new Map();
  for (const r of trainRows) {
    latest.set(r.user, Math.max(latest.get(r.user) ?? -Infinity, r.time));
  }
  return validRows.filter((r) => (latest.get(r.user) ?? -Infinity) > r.time).length;
}
