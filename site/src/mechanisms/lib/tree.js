// CART regression trees. Growth is greedy and best-first: of all current leaves, the one whose
// best split removes the most squared error is split next, so the first k splits are the
// tree a reader steps through. Pruning is cost-complexity (weakest link): the subtree whose
// collapse costs the least error per leaf removed goes first, giving a nested sequence.

function summary(ys) {
  const n = ys.length;
  const mean = ys.reduce((s, y) => s + y, 0) / n;
  const sse = ys.reduce((s, y) => s + (y - mean) ** 2, 0);
  return { n, mean, sse };
}

// Every midpoint between distinct sorted values, with the SSE of the two sides it creates.
export function splitCurve(rows, ys, feature, minLeaf) {
  const order = rows.map((_, i) => i).sort((a, b) => rows[a][feature] - rows[b][feature]);
  const n = order.length;
  let leftSum = 0;
  let leftSquares = 0;
  const total = order.reduce((s, i) => s + ys[i], 0);
  const squares = order.reduce((s, i) => s + ys[i] * ys[i], 0);
  const points = [];
  for (let k = 0; k < n - 1; k += 1) {
    const y = ys[order[k]];
    leftSum += y;
    leftSquares += y * y;
    const here = rows[order[k]][feature];
    const next = rows[order[k + 1]][feature];
    const left = k + 1;
    const right = n - left;
    if (here === next || left < minLeaf || right < minLeaf) continue;
    const rightSum = total - leftSum;
    const leftSse = leftSquares - (leftSum * leftSum) / left;
    const rightSse = squares - leftSquares - (rightSum * rightSum) / right;
    const sse = leftSse + rightSse;
    points.push({ threshold: (here + next) / 2, sse });
  }
  return points;
}

function bestSplit(rows, ys, features, minLeaf) {
  let best = null;
  for (const feature of features) {
    for (const point of splitCurve(rows, ys, feature, minLeaf)) {
      if (!best || point.sse < best.sse) best = { feature, ...point };
    }
  }
  return best;
}

export function grow(rows, features, { minLeaf = 5, maxSplits = 200 } = {}) {
  const ys = rows.map((row) => row.rating);
  const nodes = [];
  const make = (indices, depth) => {
    const node = { id: nodes.length, depth, indices, ...summary(indices.map((i) => ys[i])) };
    const subset = indices.map((i) => rows[i]);
    node.split = bestSplit(subset, indices.map((i) => ys[i]), features, minLeaf);
    nodes.push(node);
    return node;
  };
  const root = make(rows.map((_, i) => i), 0);
  const frontier = [root];
  let order = 0;
  while (order < maxSplits) {
    const candidates = frontier.filter((node) => node.split && node.sse - node.split.sse > 1e-12);
    if (candidates.length === 0) break;
    const node = candidates.reduce((a, b) => (b.sse - b.split.sse > a.sse - a.split.sse ? b : a));
    frontier.splice(frontier.indexOf(node), 1);
    const { feature, threshold } = node.split;
    node.feature = feature;
    node.threshold = threshold;
    node.order = order;
    order += 1;
    node.left = make(node.indices.filter((i) => rows[i][feature] <= threshold), node.depth + 1);
    node.right = make(node.indices.filter((i) => rows[i][feature] > threshold), node.depth + 1);
    frontier.push(node.left, node.right);
  }
  return { root, nodes, splits: order };
}

// A view of the tree that keeps only the first `steps` splits and treats every node in
// `collapsed` as a leaf.
export function view(tree, { steps = Infinity, collapsed = new Set() } = {}) {
  const open = (node) => node.left && node.order < steps && !collapsed.has(node.id);
  const leafFor = (row) => {
    let node = tree.root;
    while (open(node)) node = row[node.feature] <= node.threshold ? node.left : node.right;
    return node;
  };
  const leaves = [];
  const walk = (node) => {
    if (open(node)) {
      walk(node.left);
      walk(node.right);
    } else leaves.push(node);
  };
  walk(tree.root);
  const internal = [];
  const gather = (node) => {
    if (!open(node)) return;
    internal.push(node);
    gather(node.left);
    gather(node.right);
  };
  gather(tree.root);
  return { predict: (row) => leafFor(row).mean, leafFor, leaves, internal, open };
}

// Weakest-link pruning on training SSE: alpha_k and the nodes collapsed by then.
export function pruningPath(tree) {
  const collapsed = new Set();
  const path = [{ alpha: 0, collapsed: new Set(), leaves: view(tree).leaves.length }];
  for (;;) {
    const current = view(tree, { collapsed });
    if (current.internal.length === 0) break;
    const below = (node) => {
      if (!current.open(node)) return { sse: node.sse, leaves: 1 };
      const left = below(node.left);
      const right = below(node.right);
      return { sse: left.sse + right.sse, leaves: left.leaves + right.leaves };
    };
    let weakest = null;
    for (const node of current.internal) {
      const subtree = below(node);
      const g = (node.sse - subtree.sse) / (subtree.leaves - 1);
      if (!weakest || g < weakest.g - 1e-12) weakest = { node, g };
    }
    collapsed.add(weakest.node.id);
    const leaves = view(tree, { collapsed }).leaves.length;
    path.push({ alpha: weakest.g, collapsed: new Set(collapsed), leaves });
  }
  return path;
}

// The subtree in effect at a given alpha: the last pruning step whose alpha is at most it.
export function atAlpha(path, alpha) {
  let chosen = path[0];
  for (const step of path) if (step.alpha <= alpha + 1e-12) chosen = step;
  return chosen;
}

// Impurity importance: the squared error each feature's splits removed, as shares.
export function impurityImportance(tree, features, steps = Infinity, collapsed = new Set()) {
  const { internal } = view(tree, { steps, collapsed });
  const totals = Object.fromEntries(features.map((f) => [f, 0]));
  for (const node of internal) totals[node.feature] += node.sse - node.left.sse - node.right.sse;
  const sum = Object.values(totals).reduce((s, v) => s + v, 0) || 1;
  return features.map((f) => totals[f] / sum);
}

// Permutation importance: the rise in RMSE on held-out rows when one feature is shuffled.
export function permutationImportance(predict, rows, features, rng, repeats = 10) {
  const rmseOf = (set) =>
    Math.sqrt(set.reduce((s, row) => s + (predict(row) - row.rating) ** 2, 0) / set.length);
  const base = rmseOf(rows);
  return features.map((feature) => {
    let total = 0;
    for (let repeat = 0; repeat < repeats; repeat += 1) {
      const values = rows.map((row) => row[feature]);
      for (let i = values.length - 1; i > 0; i -= 1) {
        const j = Math.floor(rng() * (i + 1));
        [values[i], values[j]] = [values[j], values[i]];
      }
      total += rmseOf(rows.map((row, i) => ({ ...row, [feature]: values[i] }))) - base;
    }
    return total / repeats;
  });
}

// Exact step surface over two features: every split threshold on either axis becomes an edge,
// each edge is repeated so neighbouring cells meet in a vertical wall, and each cell is flat.
export function stepSurface(predict, xKey, yKey, xRange, yRange, thresholds, fixed) {
  const edges = (key, [low, high]) => [
    low,
    ...[...new Set(thresholds.filter((t) => t.feature === key).map((t) => t.value))]
      .filter((v) => v > low && v < high)
      .sort((a, b) => a - b),
    high,
  ];
  const xs = edges(xKey, xRange);
  const ys = edges(yKey, yRange);
  const doubled = (list) => list.slice(0, -1).flatMap((v, i) => [v, list[i + 1]]);
  const cell = (list, index) => (list[Math.floor(index / 2)] + list[Math.floor(index / 2) + 1]) / 2;
  const x = doubled(xs);
  const y = doubled(ys);
  const z = y.map((_, r) =>
    x.map((__, c) => predict({ ...fixed, [xKey]: cell(xs, c), [yKey]: cell(ys, r) })),
  );
  return { x, y, z };
}
