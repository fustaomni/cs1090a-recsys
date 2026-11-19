// site/src/mechanisms/lib/moepipeline.js
// A.359: the mixture of experts end to end on the three windows. The experts are fitted on
// train and scored on validate, where the gate is fitted; then, as a final model is refit on
// all development data, the experts are refit on train plus validate and the mixture is
// scored once on test, its gate features read from train plus validate only.

import { bucketOf } from "./moe.js";
import {
  arrivingRatings,
  fitGate,
  gateWeights,
  threeWindows,
  topK,
  utilisation,
  windowFeatures,
} from "./moefit.js";

export const EXPERT_NAMES = ["Shared bias", "Movie mean", "Regularised linear", "kNN"];

const clip = (value) => Math.min(5, Math.max(1, value));

// The four experts from one history: the mean rating; the mean plus a shrunk movie effect; the
// mean plus shrunk user and movie effects; and the mean rating of the k history ratings nearest
// in (user effect, movie effect). An effect never seen in the history is zero.
export function fitExperts(history, { shrink = 10, k = 25 } = {}) {
  if (history.length === 0) throw new Error("the experts need at least one history rating");
  const latest = Math.max(...history.map((row) => row.time));
  const mu = history.reduce((sum, row) => sum + row.rating, 0) / history.length;
  const effect = (key, residual) => {
    const totals = new Map();
    history.forEach((row) => {
      const [total, n] = totals.get(row[key]) ?? [0, 0];
      totals.set(row[key], [total + residual(row), n + 1]);
    });
    const shrunk = new Map();
    totals.forEach(([total, n], id) => shrunk.set(id, total / (n + shrink)));
    return (id) => shrunk.get(id) ?? 0;
  };
  const movie = effect("movie", (row) => row.rating - mu);
  const user = effect("user", (row) => row.rating - mu - movie(row.movie));
  const points = history.map((row) => [user(row.user), movie(row.movie), row.rating]);
  // The k nearest kept in a sorted array of at most k, so a query costs n times k, not a sort.
  // Ratings sharing a user and a movie share a query, so each is answered once.
  const answered = new Map();
  const neighbours = (u, m) => {
    const key = `${u},${m}`;
    if (answered.has(key)) return answered.get(key);
    const nearest = [];
    points.forEach(([pu, pm, rating]) => {
      const distance = (pu - u) ** 2 + (pm - m) ** 2;
      if (nearest.length === k && distance >= nearest[k - 1][0]) return;
      let at = nearest.length;
      while (at > 0 && nearest[at - 1][0] > distance) at -= 1;
      nearest.splice(at, 0, [distance, rating]);
      if (nearest.length > k) nearest.pop();
    });
    const value = nearest.reduce((sum, [, rating]) => sum + rating, 0) / nearest.length;
    answered.set(key, value);
    return value;
  };
  return {
    predict(rows) {
      if (rows.some((row) => row.time <= latest)) {
        throw new Error("leakage: an expert is asked about a rating its history already reaches");
      }
      return rows.map((row) => {
        const u = user(row.user);
        const m = movie(row.movie);
        return [mu, clip(mu + m), clip(mu + u + m), clip(neighbours(u, m))];
      });
    },
  };
}

const rmse = (predicted, rows) =>
  Math.sqrt(
    predicted.reduce((sum, value, i) => sum + (value - rows[i].rating) ** 2, 0) / rows.length,
  );
const column = (matrix, j) => matrix.map((row) => row[j]);
const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;

// The fitted run: experts fitted on train and scored on validate, where the gate is fitted at
// temperature 1 with every expert; then experts refit on train plus validate, scored once on test.
export function runMixture({ seed = 191, validateFrom = 600, testFrom = 800 } = {}) {
  const { train, validate, test } = threeWindows(arrivingRatings({ seed }), {
    validateFrom,
    testFrom,
  });
  const validateFeatures = windowFeatures(train, validate);
  const validateExperts = fitExperts(train).predict(validate);
  const { theta, losses } = fitGate({
    features: validateFeatures,
    predictions: validateExperts,
    targets: validate.map((row) => row.rating),
  });
  const development = [...train, ...validate];
  const testFeatures = windowFeatures(development, test);
  const testExperts = fitExperts(development).predict(test);
  const run = {
    windows: { train: train.length, validate: validate.length, test: test.length },
    theta,
    losses,
    validate: { rows: validate, features: validateFeatures, experts: validateExperts },
    test: { rows: test, features: testFeatures, experts: testExperts },
  };
  return { ...run, ...reweigh(run) };
}

// The same fitted gate read at another temperature, or cut to its k largest weights: a lab may
// sharpen, soften or sparsify the gate without refitting it.
export function reweigh(run, { temperature = 1, k = null } = {}) {
  const weigh = (feature) => {
    const weights = gateWeights(run.theta, feature, temperature);
    return k === null ? weights : topK(weights, k);
  };
  const score = ({ rows, features, experts }) => {
    const weights = features.map(weigh);
    const mixture = weights.map((w, i) => w.reduce((sum, v, j) => sum + v * experts[i][j], 0));
    return {
      weights,
      mixture,
      rmse: {
        experts: EXPERT_NAMES.map((_, j) => rmse(column(experts, j), rows)),
        uniform: rmse(experts.map(mean), rows),
        mixture: rmse(mixture, rows),
      },
    };
  };
  const validation = score(run.validate);
  const tested = score(run.test);
  return {
    validation: validation.rmse,
    tested: tested.rmse,
    utilisation: utilisation(tested.weights),
    rows: run.test.rows.map((row, i) => ({
      ...row,
      bucket: bucketOf(run.test.features[i]),
      experts: run.test.experts[i],
      mixture: tested.mixture[i],
      weights: tested.weights[i],
    })),
  };
}
