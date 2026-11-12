// site/src/ExampleRecord.jsx
// An illustrative prediction evidence record beside its separate outcome record (A.301).
import data from "./data/project.json";
import { bind } from "./bind.js";

function Fields({ rows }) {
  return (
    <dl>
      {rows.map(([name, value]) => (
        <div key={name}>
          <dt>{name}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function ExampleRecord() {
  const record = data.example_record;
  return (
    <div className="opponent">
      <p className="eyebrow">{record.label}</p>
      <h3>
        User {record.user} to movie {record.movie}{" "}
        <span className="badge planned">Simulated example</span>
      </h3>
      <p>
        Predicted rating <strong>{record.predicted}</strong> by {bind(record.model)}
      </p>
      <div className="two-col">
        <div className="panel">
          <h4>Prediction record, written when the prediction is made</h4>
          <Fields rows={record.prediction_fields} />
        </div>
        <div className="panel">
          <h4>Outcome record, written only when the ground truth is observed</h4>
          <Fields rows={record.outcome_fields} />
        </div>
      </div>
      <p className="muted">{record.note}</p>
    </div>
  );
}
