// site/src/EvidenceChain.jsx
// The evidence chain each page states, read from project.json and never typed in (A.282).
import data from "./data/project.json";

const BADGE = { "in place": "done", planned: "planned", "outside the TF's scope": "" };

export default function EvidenceChain({ page }) {
  const { evidence } = data;
  const stated = evidence.pages[page];
  const byId = Object.fromEntries(evidence.disciplines.map((entry) => [entry.id, entry]));
  return (
    <aside className="opponent" aria-label="How this page's conclusions are decided">
      <p className="eyebrow">Evidence chain, offline and within the TF's scope</p>
      <ul className="chips">
        {evidence.chain.map((stage) => (
          <li key={stage}>{stage}</li>
        ))}
      </ul>
      <p>{stated.note}</p>
      <dl>
        {stated.disciplines.map((id) => {
          const entry = byId[id];
          const outside = entry.status === "outside the TF's scope";
          return (
            <div key={id}>
              <dt>
                {entry.id}. {entry.name} <span className={`badge ${BADGE[entry.status]}`}>{entry.status}</span>
              </dt>
              <dd>
                {entry.question} {entry.now} {outside ? entry.why : `Delivered by ${entry.steps.join(", ")}.`}
              </dd>
            </div>
          );
        })}
      </dl>
    </aside>
  );
}
