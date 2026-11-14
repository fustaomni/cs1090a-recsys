// site/src/ResearchQuestions.jsx
// The three research questions, and which MovieLens 1M can answer (A.306).
import data from "./data/project.json";

export default function ResearchQuestions() {
  return (
    <div className="opponent">
      <h2>Three research questions</h2>
      <dl>
        {data.research_questions.map((entry) => (
          <div key={entry.id}>
            <dt>
              {entry.id}. {entry.question}{" "}
              <span className={`badge ${entry.answerable === "Not established" ? "" : "done"}`}>
                {entry.answerable}
              </span>
            </dt>
            <dd>
              {entry.role}. Evidence: {entry.evidence}.
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
