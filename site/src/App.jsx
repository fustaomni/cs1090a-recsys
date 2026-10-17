import { useEffect, useState } from "react";
import data from "./data/project.json";
import results from "./data/results.json";
import Mechanisms from "./mechanisms/Mechanisms.jsx";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "scope", label: "Scope" },
  { id: "phases", label: "Phases" },
  { id: "deploys", label: "Models & techniques" },
  { id: "mechanisms", label: "Interactive mechanisms" },
  { id: "results", label: "Results" },
];

const STATUS_LABEL = { done: "Done", current: "In progress", planned: "Planned" };

const JOIN = `mailto:${data.contact}?subject=${encodeURIComponent(
  "Joining the MovieLens recommender project",
)}`;

// One page per section, chosen by the URL hash, so each link shows only its own content
// and #overview, #scope and the rest stay shareable.
function currentPage() {
  const id = window.location.hash.slice(1);
  return SECTIONS.some((section) => section.id === id) ? id : "overview";
}

function useHashPage() {
  const [page, setPage] = useState(currentPage);
  useEffect(() => {
    const change = () => {
      setPage(currentPage());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  return page;
}

function GroupCard() {
  const { group } = data;
  const seats = Array.from({ length: group.seats }, (_, index) => group.members[index]);
  return (
    <aside className="group-card" aria-label={`Project Group #${group.number}`}>
      <p className="group-number">Project Group #{group.number}</p>
      <p className="group-title">{data.title}</p>
      <p className="group-label">Group members:</p>
      <ol>
        {seats.map((member, index) =>
          member ? (
            <li key={member}>{member}</li>
          ) : (
            <li key={`open-${index}`} className="open">
              <a href={JOIN}>Open seat · join us</a>
            </li>
          ),
        )}
      </ol>
    </aside>
  );
}

function Overview() {
  const { overview, milestones, join } = data;
  return (
    <section id="overview" className="section">
      <GroupCard />
      <p className="eyebrow">MovieLens 1M · offline · leakage-safe</p>
      <h1>{data.title}</h1>
      <p className="lede">{overview.question}</p>
      <div className="hero-cta">
        <a className="cta" href={JOIN}>
          Join the team
        </a>
        <p className="cta-note">
          Looking for two to four teammates. The design, the split and the evaluation are
          already done: you own one block of phases end to end.
        </p>
      </div>
      <p>{overview.summary}</p>
      <ul className="stats">
        {overview.stats.map((stat) => (
          <li key={stat.label}>
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </li>
        ))}
      </ul>
      <h2>Roadmap to December</h2>
      <ol className="timeline">
        {milestones.map((milestone) => (
          <li key={milestone.id}>
            <p className="when">{milestone.due}</p>
            <h3>{milestone.name}</h3>
            <p>{milestone.focus}</p>
            <p className="phases">Phases {milestone.phases}</p>
          </li>
        ))}
      </ol>
      <div className="join">
        <h2>{join.title}</h2>
        <p>{join.need}</p>
        <ul>
          {join.roles.map((role) => (
            <li key={role.name}>
              <strong>{role.name}</strong> — {role.owns}
            </li>
          ))}
        </ul>
        <a className="cta" href={JOIN}>
          Email the group to join
        </a>
      </div>
    </section>
  );
}

function Scope() {
  const { scope } = data;
  return (
    <section id="scope" className="section">
      <h2>Scope, after review</h2>
      <p className="lede">{scope.principle}</p>
      <div className="two-col">
        <div className="panel">
          <h3>Removed by the reviewer</h3>
          <dl>
            {scope.removed.map((entry) => (
              <div key={entry.item}>
                <dt>{entry.item}</dt>
                <dd>{entry.why}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="panel">
          <h3>Retained and reframed</h3>
          <dl>
            {scope.retained.map((entry) => (
              <div key={entry.item}>
                <dt>{entry.item}</dt>
                <dd>{entry.form}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}

function Phases() {
  const byId = Object.fromEntries(data.phases.map((phase) => [phase.id, phase]));
  const groups = data.milestones.filter((milestone) => milestone.phase_ids.length > 0);
  const opened = groups[0]?.phase_ids[0];
  return (
    <section id="phases" className="section">
      <h2>The phases</h2>
      <p className="status-line">
        <span className="badge current">Status</span> {data.status}
      </p>
      {groups.map((milestone) => (
        <div key={milestone.id} className="milestone-group">
          <h3>
            {milestone.id} · {milestone.name} <span className="when">{milestone.due}</span>
          </h3>
          <ol className="phase-list">
            {milestone.phase_ids.map((id) => (
              <li key={id}>
                <details open={id === opened}>
                  <summary>
                    <span className="phase-id">Phase {id}</span>
                    <span className="phase-title">{byId[id].title}</span>
                    <span className={`badge ${milestone.status}`}>
                      {STATUS_LABEL[milestone.status]}
                    </span>
                  </summary>
                  <ul>
                    {byId[id].points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </details>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </section>
  );
}

function Deploys() {
  const groups = [];
  for (const model of data.models) {
    const last = groups[groups.length - 1];
    if (last && last.phase === model.phase) {
      last.models.push(model);
    } else {
      groups.push({ phase: model.phase, models: [model] });
    }
  }
  return (
    <section id="deploys" className="section">
      <h2>What the project deploys</h2>
      <h3>Twelve predictive models, simplest first</h3>
      <ol className="ladder">
        {groups.map((group) => (
          <li key={group.phase}>
            <p className="eyebrow">
              Phase {group.phase} · {data.families[group.phase]}
            </p>
            <ul className="rungs">
              {group.models.map((model) => (
                <li key={model.id}>
                  <span className="rung-id">{model.id}</span>
                  {model.name}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
      <div className="opponent">
        <h3>The opponent every model must beat</h3>
        <ul className="chips">
          {data.baselines.map((baseline) => (
            <li key={baseline.name}>{baseline.name}</li>
          ))}
        </ul>
        <p>{data.baseline_note}</p>
      </div>
      <h3>Ten supporting techniques</h3>
      <ul className="cards">
        {data.techniques.map((technique) => (
          <li key={technique.id}>
            <p className="eyebrow">Technique {technique.id}</p>
            <h4>{technique.name}</h4>
            <p className="muted">{technique.where}</p>
          </li>
        ))}
      </ul>
      <h3>Deliberately excluded</h3>
      <ul>
        {data.excluded.map((entry) => (
          <li key={entry}>{entry}</li>
        ))}
      </ul>
    </section>
  );
}

const METRICS = [
  ["rmse", "RMSE"],
  ["mae", "MAE"],
  ["rmsem", "RMSEM"],
  ["maem", "MAEM"],
];

function estimate(metric) {
  return `${metric.value.toFixed(3)} [${metric.low.toFixed(3)}, ${metric.high.toFixed(3)}]`;
}

function Results() {
  const { primary, rows } = results;
  return (
    <section id="results" className="section">
      <h2>Results</h2>
      <p className="muted">
        {results.protocol}. Updated {results.updated}.
      </p>
      <div className="opponent">
        <p className="status-line">
          <span className={`badge ${primary.status === "decided" ? "done" : "current"}`}>
            {primary.status === "decided" ? "Decided" : "Pending"}
          </span>
          <strong>Primary comparison, fixed before any result</strong>
        </p>
        <p>{primary.question}</p>
        <ul className="verdicts">
          {primary.verdicts.map((verdict) => (
            <li key={verdict} className={verdict === primary.verdict ? "chosen" : ""}>
              {verdict}
            </li>
          ))}
        </ul>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Baseline or model</th>
              {METRICS.map(([key, label]) => (
                <th key={key} scope="col">
                  {label}
                </th>
              ))}
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className={row.kind}>
                <th scope="row">{row.name}</th>
                {METRICS.map(([key]) => (
                  <td key={key}>{row.metrics ? estimate(row.metrics[key]) : "—"}</td>
                ))}
                <td>
                  <span className={`badge ${row.status === "measured" ? "done" : "planned"}`}>
                    {row.status === "measured" ? "Measured" : `Pending · ${row.milestone}`}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        Intervals are 95%, from a bootstrap clustered by user. Each is descriptive, not a test:
        only the primary comparison above is tested, paired, as pre-registered.
      </p>
    </section>
  );
}

const READY = {
  overview: Overview,
  scope: Scope,
  phases: Phases,
  deploys: Deploys,
  mechanisms: Mechanisms,
  results: Results,
};

export default function App() {
  const page = useHashPage();
  const Page = READY[page];
  return (
    <>
      <header className="bar">
        <a href="#overview" className="brand">
          Rating recommender
        </a>
        <nav>
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              aria-current={section.id === page ? "page" : undefined}
            >
              {section.label}
            </a>
          ))}
        </nav>
        <a className="cta small" href={JOIN}>
          Join the team
        </a>
      </header>
      <main>
        <Page />
      </main>
      <footer className="foot">
        Project Group #{data.group.number} · updated at every milestone
      </footer>
    </>
  );
}
