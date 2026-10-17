// k-nearest-neighbour regression: no equation is learned; a prediction is the mean rating of
// the k training rows nearest the query under the chosen distance.

export function euclidean(a, b) {
  let total = 0;
  for (let j = 0; j < a.length; j += 1) total += (a[j] - b[j]) ** 2;
  return Math.sqrt(total);
}

export function manhattan(a, b) {
  let total = 0;
  for (let j = 0; j < a.length; j += 1) total += Math.abs(a[j] - b[j]);
  return total;
}

// Gower's distance for mixed types: each numeric feature contributes |a - b| / range and each
// categorical one contributes 0 or 1, averaged over all features, so it lies in [0, 1].
export function gower(ranges, categorical) {
  const count = ranges.length + categorical.length;
  return (a, b) => {
    let total = 0;
    ranges.forEach((range, j) => {
      total += Math.abs(a[j] - b[j]) / range;
    });
    categorical.forEach((j) => {
      total += a[j] === b[j] ? 0 : 1;
    });
    return total / count;
  };
}

// Brute force: every training row's distance, sorted, the first k kept.
export function nearest(points, query, k, distance) {
  return points
    .map((point, index) => ({ index, distance: distance(point, query) }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, k);
}

export function predict(points, ratings, query, k, distance) {
  const found = nearest(points, query, k, distance);
  return found.reduce((total, hit) => total + ratings[hit.index], 0) / found.length;
}

// A k-d tree for Euclidean search: split on one axis per level at the median, and skip any
// branch whose splitting plane is farther than the current k-th nearest distance.
export function kdTree(points) {
  const build = (indices, depth) => {
    if (indices.length === 0) return null;
    const axis = depth % points[0].length;
    indices.sort((a, b) => points[a][axis] - points[b][axis]);
    const middle = Math.floor(indices.length / 2);
    return {
      index: indices[middle],
      axis,
      left: build(indices.slice(0, middle), depth + 1),
      right: build(indices.slice(middle + 1), depth + 1),
    };
  };
  return build(points.map((_, index) => index), 0);
}

export function kdNearest(tree, points, query, k) {
  const best = [];
  let visited = 0;
  const offer = (index) => {
    visited += 1;
    const distance = euclidean(points[index], query);
    if (best.length < k || distance < best[best.length - 1].distance) {
      best.push({ index, distance });
      best.sort((a, b) => a.distance - b.distance);
      if (best.length > k) best.pop();
    }
  };
  const search = (node) => {
    if (!node) return;
    offer(node.index);
    const gap = query[node.axis] - points[node.index][node.axis];
    const [near, far] = gap < 0 ? [node.left, node.right] : [node.right, node.left];
    search(near);
    if (best.length < k || Math.abs(gap) < best[best.length - 1].distance) search(far);
  };
  search(tree);
  return { neighbours: best, visited };
}

// Distance concentration: (largest - smallest) / smallest distance from one query.
export function relativeContrast(points, query, distance) {
  const distances = points.map((point) => distance(point, query));
  const low = Math.min(...distances);
  return (Math.max(...distances) - low) / low;
}

// Counts of values in equal-width bins between low and high.
export function histogram(values, low, high, bins) {
  const counts = new Array(bins).fill(0);
  const width = (high - low) / bins;
  for (const value of values) {
    const slot = Math.min(bins - 1, Math.max(0, Math.floor((value - low) / width)));
    counts[slot] += 1;
  }
  return counts.map((count, slot) => ({
    from: low + slot * width,
    to: low + (slot + 1) * width,
    count,
  }));
}
