// site/src/Objective.jsx
// The research objective and the three meanings of why, each with its steps (A.308).
import data from "./data/project.json";

export default function Objective() {
  const { objective } = data;
  return (
    <div className="opponent">
      <h2>Research objective</h2>
      <p className="lede">{objective.statement}</p>
      <dl>
        {objective.whys.map((entry) => (
          <div key={entry.why}>
            <dt>{entry.why}</dt>
            <dd>
              {entry.answer} Delivered by {entry.steps.join(", ")}.
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
