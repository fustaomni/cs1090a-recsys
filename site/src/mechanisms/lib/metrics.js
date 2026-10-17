// Errors reported both unclipped and clipped to [1, 5], with the count of predictions outside.

export function rmse(predictions, actual) {
  const total = predictions.reduce((sum, p, index) => sum + (p - actual[index]) ** 2, 0);
  return Math.sqrt(total / predictions.length);
}

export function clip(value) {
  return Math.min(5, Math.max(1, value));
}

export function outOfRange(predictions) {
  return predictions.filter((p) => p < 1 || p > 5).length;
}
