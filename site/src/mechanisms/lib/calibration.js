// Two views of how predictions relate to ratings. Error by true level always slants for a
// squared-error predictor, because even E[Y | X] pulls the extremes toward the mean.
// Calibration bins rows by predicted value and compares the mean actual rating: a slope
// near one means the shrinkage is the inevitable kind; a slope above one means the
// predictions are flatter than the data supports.

export function errorByLevel(predictions, actual) {
  return [1, 2, 3, 4, 5].map((level) => {
    const residuals = actual
      .map((y, i) => [y, predictions[i] - y])
      .filter(([y]) => y === level)
      .map(([, r]) => r);
    const total = residuals.reduce((s, r) => s + r, 0);
    const mean = residuals.length ? total / residuals.length : NaN;
    return { level, count: residuals.length, mean };
  });
}

// Equal-count bins of the predicted value, each with its mean prediction and mean rating.
export function calibrationBins(predictions, actual, bins = 8) {
  const order = predictions.map((_, i) => i).sort((a, b) => predictions[a] - predictions[b]);
  return Array.from({ length: bins }, (_, b) => {
    const members = order.slice(
      Math.floor((b * order.length) / bins),
      Math.floor(((b + 1) * order.length) / bins),
    );
    const mean = (values) => values.reduce((s, v) => s + v, 0) / values.length;
    return {
      predicted: mean(members.map((i) => predictions[i])),
      actual: mean(members.map((i) => actual[i])),
    };
  });
}

// Least-squares slope of the actual rating on the prediction, over all rows.
export function calibrationSlope(predictions, actual) {
  const n = predictions.length;
  const mp = predictions.reduce((s, v) => s + v, 0) / n;
  const ma = actual.reduce((s, v) => s + v, 0) / n;
  let sxy = 0;
  let sxx = 0;
  for (let i = 0; i < n; i += 1) {
    sxy += (predictions[i] - mp) * (actual[i] - ma);
    sxx += (predictions[i] - mp) ** 2;
  }
  return sxx > 1e-9 * n ? sxy / sxx : NaN;
}

// Bias squared, variance and noise at query points, across fits to independent datasets that
// share a known true function: possible only on synthetic data.
export function decomposition(fits, queries, truth, noise) {
  let bias = 0;
  let variance = 0;
  queries.forEach((query) => {
    const values = fits.map((predict) => predict(query));
    const centre = values.reduce((s, v) => s + v, 0) / values.length;
    bias += (centre - truth(query)) ** 2;
    variance += values.reduce((s, v) => s + (v - centre) ** 2, 0) / values.length;
  });
  return { bias: bias / queries.length, variance: variance / queries.length, noise };
}
