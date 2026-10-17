// A surface sampled on an even grid: z[row][column] with rows along y, as Plotly expects.

export function steps(low, high, count) {
  return Array.from({ length: count }, (_, index) => low + ((high - low) * index) / (count - 1));
}

export function surface(xs, ys, height) {
  return ys.map((y) => xs.map((x) => height(x, y)));
}
