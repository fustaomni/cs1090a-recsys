// site/src/Architecture.jsx
// The research architecture, read from project.json: its flow, decisions and components (A.298).
import data from "./data/project.json";
import { bind } from "./bind.js";

export default function Architecture() {
  const { architecture } = data;
  return (
    <div className="opponent">
      <h3>How every result is decided</h3>
      <ol className="timeline">
        {architecture.flow.map((stage) => (
          <li key={stage}>{bind(stage)}</li>
        ))}
      </ol>
      <ul className="chips">
        {architecture.outcomes.map((outcome) => (
          <li key={outcome.verdict}>{outcome.decision}</li>
        ))}
      </ul>
      <dl>
        {architecture.components.map((entry) => (
          <div key={entry.name}>
            <dt>
              {entry.id}. {entry.name}
            </dt>
            <dd>
              {entry.records}. Implementation: {entry.tools}. Built by {entry.steps.join(", ")}.
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
