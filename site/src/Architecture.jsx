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
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Component</th>
              <th scope="col">What it records or does</th>
              <th scope="col">Implementation</th>
              <th scope="col">Step</th>
            </tr>
          </thead>
          <tbody>
            {architecture.components.map((entry) => (
              <tr key={entry.name}>
                <th scope="row">
                  {entry.id}. {entry.name}
                </th>
                <td>{entry.records}</td>
                <td>{entry.tools}</td>
                <td>{entry.steps.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
