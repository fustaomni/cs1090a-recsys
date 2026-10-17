// A labelled range input that shows its current value.
const twoPlaces = (value) => value.toFixed(2);

export default function Slider({ label, value, min, max, step, onChange, format = twoPlaces }) {
  return (
    <label className="control">
      <span>
        {label} <strong>{format(value)}</strong>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
