// A number to fixed places, never printed as "-0.000".
export function fixed(value, places = 3) {
  const text = value.toFixed(places);
  return Number(text) === 0 ? (0).toFixed(places) : text;
}
