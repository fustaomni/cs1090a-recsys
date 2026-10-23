// Where a lab's numbers come from (A.100): a fitted value means nothing without the data,
// split, features, preparation and method behind it, so every lab states them beside it.
const FIELDS = [
  ["data", "Data"],
  ["split", "Split"],
  ["features", "Features"],
  ["preparation", "Preparation"],
  ["method", "Method"],
];

export default function Provenance(props) {
  const shown = FIELDS.filter(([key]) => props[key]);
  return (
    <aside className="provenance" aria-label="Where these numbers come from">
      <h4>Where these numbers come from</h4>
      <dl className="readouts">
        {shown.map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>{props[key]}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
