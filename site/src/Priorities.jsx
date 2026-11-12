// site/src/Priorities.jsx
// The delivery priorities to December 10, by necessity, each with its steps (A.308).
import data from "./data/project.json";

const BADGE = { Essential: "current", "Useful extension": "planned", "Future research": "" };

export default function Priorities() {
  return (
    <div className="opponent">
      <h3>Priorities to December 10</h3>
      <ol>
        {data.priorities.map((entry) => (
          <li key={entry.name}>
            <strong>{entry.name}</strong>{" "}
            <span className={`badge ${BADGE[entry.necessity]}`}>{entry.necessity}</span>{" "}
            {entry.what}
            {entry.steps.length > 0 ? ` Delivered by ${entry.steps.join(", ")}.` : ""}
          </li>
        ))}
      </ol>
    </div>
  );
}
