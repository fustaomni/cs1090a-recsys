// Boosting with the CART trees in tree.js.
//
// AdaBoost.R2 (Drucker 1997): each round draws rows in proportion to their weights, fits a
// shallow tree, scores every row's loss as its error over the round's largest error D, and
// sets beta = Lbar / (1 - Lbar) from the weighted average loss. Rows the tree predicted well
// are down-weighted by beta^(1 - L); the ensemble predicts the weighted median of its trees,
// each tree weighted by log(1 / beta). A round whose Lbar reaches 0.5 stops the boosting.
//
// Gradient boosting (Friedman 2001): start from the mean (squared loss) or median (absolute
// loss); each stage fits a tree to the negative gradient, the residual y - F for squared loss
// and its sign for absolute loss, and adds the tree scaled by the learning rate.

import { mulberry32 } from "./random.js";
import { grow, view } from "./tree.js";

const LOSSES = {
  linear: (x) => x,
  square: (x) => x * x,
  exponential: (x) => 1 - Math.exp(-x),
};

export function weightedMedian(values, weights) {
  const order = values.map((_, i) => i).sort((a, b) => values[a] - values[b]);
  const total = weights.reduce((s, w) => s + w, 0);
  let running = 0;
  for (const i of order) {
    running += weights[i];
    if (running >= total / 2) return values[i];
  }
  return values[order[order.length - 1]];
}

function draw(weights, rng) {
  const cumulative = [];
  let running = 0;
  for (const w of weights) {
    running += w;
    cumulative.push(running);
  }
  return weights.map(() => {
    const target = rng() * running;
    let low = 0;
    let high = cumulative.length - 1;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (cumulative[middle] < target) low = middle + 1;
      else high = middle;
    }
    return low;
  });
}

export function adaBoostR2(rows, features, options = {}) {
  const { rounds = 30, splits = 3, loss = "linear", learningRate = 1 } = options;
  const { seed = 1 } = options;
  const rng = mulberry32(seed);
  const n = rows.length;
  let weights = new Array(n).fill(1 / n);
  const history = [];
  for (let round = 0; round < rounds; round += 1) {
    const picked = draw(weights, rng);
    const model = view(
      grow(
        picked.map((i) => rows[i]),
        features,
        { minLeaf: 5, maxSplits: splits },
      ),
    );
    const errors = rows.map((row) => Math.abs(model.predict(row) - row.rating));
    const largest = Math.max(...errors);
    const losses = errors.map((e) => (largest > 0 ? LOSSES[loss](e / largest) : 0));
    const average = losses.reduce((s, l, i) => s + l * weights[i], 0);
    if (average >= 0.5) {
      history.push({ stopped: true, average, largest, weights: weights.slice() });
      break;
    }
    const beta = Math.max(average, 1e-12) / (1 - average);
    const updated = weights.map((w, i) => w * beta ** ((1 - losses[i]) * learningRate));
    const total = updated.reduce((s, w) => s + w, 0);
    weights = updated.map((w) => w / total);
    history.push({
      model,
      largest,
      average,
      beta,
      weight: learningRate * Math.log(1 / beta),
      losses,
      weights: weights.slice(),
    });
  }
  const fitted = history.filter((step) => !step.stopped);
  const predict = (row, count = fitted.length) =>
    weightedMedian(
      fitted.slice(0, count).map((step) => step.model.predict(row)),
      fitted.slice(0, count).map((step) => step.weight),
    );
  return { history, fitted, predict };
}

function median(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  const middle = sorted.length >> 1;
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function gradientBoost(rows, features, options = {}) {
  const { stages = 100, learningRate = 0.1, splits = 4, subsample = 1, seed = 1 } = options;
  const { loss = "squared" } = options;
  const rng = mulberry32(seed);
  const ys = rows.map((row) => row.rating);
  const start = loss === "squared" ? ys.reduce((s, y) => s + y, 0) / ys.length : median(ys);
  const current = ys.map(() => start);
  const steps = [];
  for (let stage = 0; stage < stages; stage += 1) {
    const residuals = ys.map((y, i) => y - current[i]);
    const gradient = residuals.map((r) => (loss === "squared" ? r : Math.sign(r)));
    let indices = rows.map((_, i) => i);
    if (subsample < 1) {
      indices = indices
        .map((i) => [rng(), i])
        .sort((a, b) => a[0] - b[0])
        .slice(0, Math.max(10, Math.round(subsample * rows.length)))
        .map(([, i]) => i);
    }
    const tree = grow(
      indices.map((i) => ({ ...rows[i], rating: gradient[i] })),
      features,
      { minLeaf: 5, maxSplits: splits },
    );
    const model = view(tree);
    const leafValue = new Map();
    for (const leaf of model.leaves) {
      const values = leaf.indices.map((k) => residuals[indices[k]]);
      leafValue.set(leaf.id, loss === "squared" ? leaf.mean : median(values));
    }
    const step = (row) => leafValue.get(model.leafFor(row).id);
    rows.forEach((row, i) => {
      current[i] += learningRate * step(row);
    });
    steps.push({ step, model, residuals });
  }
  const predict = (row, count = steps.length) => {
    let value = start;
    for (let k = 0; k < count; k += 1) value += learningRate * steps[k].step(row);
    return value;
  };
  return { start, steps, predict, learningRate };
}

// Early stopping: track the error after every stage on a later window, and stop once it has
// not improved for `patience` stages; the model kept is the one at the best stage.
export function earlyStopping(errors, patience) {
  let best = 0;
  for (let stage = 1; stage < errors.length; stage += 1) {
    if (errors[stage] < errors[best]) best = stage;
    else if (stage - best >= patience) return { best, stoppedAt: stage };
  }
  return { best, stoppedAt: errors.length - 1 };
}
