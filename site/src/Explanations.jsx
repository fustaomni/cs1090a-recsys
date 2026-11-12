// site/src/Explanations.jsx
// How each model family's prediction is explained, and the check the explanation must pass (A.315).
import data from "./data/project.json";

export default function Explanations() {
  return (
    <div className="opponent">
      <h3>How each prediction is explained</h3>
      <dl>
        {data.explanations.map((entry) => (
          <div key={entry.family}>
            <dt>{entry.family}</dt>
            <dd>
              {entry.explanation} Check: {entry.check}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
